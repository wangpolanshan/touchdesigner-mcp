"""
TouchDesigner MCP Bridge installer.
Run inside TouchDesigner Textport during development, or use work/build_tox.py to export a draggable .tox component.
"""

import secrets

BRIDGE_PATH = "/project1/td_mcp_bridge"
DEFAULT_PORT = 9980

CALLBACKS_CODE = r'''
import fnmatch
import json
import traceback

_ACTIVE_BRIDGE = None


def _set_active_bridge(webServerDAT):
    global _ACTIVE_BRIDGE
    _ACTIVE_BRIDGE = webServerDAT.parent()
    return _ACTIVE_BRIDGE


def _bridge():
    if _ACTIVE_BRIDGE is not None:
        return _ACTIVE_BRIDGE
    try:
        return me.parent()
    except Exception:
        return None


def _bridge_path():
    bridge = _bridge()
    return bridge.path if bridge is not None else ""


def _par(owner, name):
    parameter = getattr(owner.par, name, None) if owner is not None else None
    if parameter is None:
        raise ValueError("Missing parameter: {}.par.{}".format(owner.path if owner else "<none>", name))
    return parameter


def _json_safe(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def _operator(path):
    target = op(path)
    if target is None:
        raise ValueError("Operator does not exist: {}".format(path))
    return target


def _op_type(target):
    return str(getattr(target, "opType", getattr(target, "OPType", "")))


def _parameter_info(parameter):
    try:
        value = parameter.eval()
    except Exception:
        value = parameter.val
    return {
        "name": parameter.name,
        "label": parameter.label,
        "page": parameter.page.name if parameter.page else "",
        "style": str(parameter.style),
        "mode": str(parameter.mode),
        "value": _json_safe(value),
        "expression": parameter.expr or "",
        "read_only": bool(parameter.readOnly),
        "default": _json_safe(parameter.default),
    }


def _operator_summary(target):
    return {
        "path": target.path,
        "name": target.name,
        "op_type": _op_type(target),
        "family": target.family,
        "node_x": target.nodeX,
        "node_y": target.nodeY,
        "children": len(target.children) if hasattr(target, "children") else 0,
    }


def _request_header(request, name):
    wanted = name.lower()
    for key, value in request.items():
        if str(key).lower() == wanted:
            return str(value)
    headers = request.get("headers", {})
    if isinstance(headers, dict):
        for key, value in headers.items():
            if str(key).lower() == wanted:
                return str(value)
    return ""


def _request_body(request):
    for key in ("data", "body"):
        value = request.get(key)
        if value is not None:
            if isinstance(value, bytes):
                return value.decode("utf-8")
            return str(value)
    return ""


def _response(response, status, payload):
    response["statusCode"] = status
    response["statusReason"] = "OK" if status < 400 else "Error"
    response["Content-Type"] = "application/json; charset=utf-8"
    response["Access-Control-Allow-Origin"] = "null"
    response["data"] = json.dumps(payload, ensure_ascii=False)
    return response


def _walk(root, max_depth):
    found = []
    queue = [(root, 0)]
    while queue:
        current, depth = queue.pop(0)
        found.append(current)
        if depth >= max_depth or not hasattr(current, "children"):
            continue
        for child in current.children:
            queue.append((child, depth + 1))
    return found


def _action_ping(args):
    return {"pong": True, "bridge_path": _bridge_path(), "frame": absTime.frame}


def _action_project_info(args):
    bridge = _bridge()
    return {
        "product": getattr(app, "product", "TouchDesigner"),
        "version": getattr(app, "version", ""),
        "build": getattr(app, "build", ""),
        "project_name": getattr(project, "name", ""),
        "project_folder": getattr(project, "folder", ""),
        "save_version": getattr(project, "saveVersion", ""),
        "save_build": getattr(project, "saveBuild", ""),
        "frame": absTime.frame,
        "fps": project.cookRate,
        "bridge_path": _bridge_path(),
        "port": bridge.op("webserver").par.port.eval(),
        "allow_python": bool(_par(bridge, "Allowpython").eval()),
    }


def _action_list_operators(args):
    root = _operator(args.get("root", "/project1"))
    pattern = str(args.get("pattern", "*")).lower()
    op_type = str(args.get("op_type", "")).lower()
    family = str(args.get("family", "")).upper()
    max_depth = max(0, min(int(args.get("max_depth", 4)), 20))
    limit = max(1, min(int(args.get("limit", 200)), 1000))
    results = []
    for target in _walk(root, max_depth):
        path_match = fnmatch.fnmatch(target.path.lower(), pattern)
        name_match = fnmatch.fnmatch(target.name.lower(), pattern)
        if not (path_match or name_match):
            continue
        if op_type and _op_type(target).lower() != op_type:
            continue
        if family and str(target.family).upper() != family:
            continue
        results.append(_operator_summary(target))
        if len(results) >= limit:
            break
    return {"operators": results, "count": len(results), "limited": len(results) >= limit}


def _action_operator_info(args):
    target = _operator(args["path"])
    result = _operator_summary(target)
    result.update({
        "parent": target.parent().path if target.parent() else None,
        "inputs": [item.path if item else None for item in target.inputs],
        "outputs": [item.path for item in target.outputs],
        "child_paths": [item.path for item in target.children] if hasattr(target, "children") else [],
        "tags": sorted(list(target.tags)),
        "comment": target.comment,
    })
    if args.get("include_parameters", False):
        limit = max(1, min(int(args.get("parameter_limit", 200)), 1000))
        result["parameters"] = [_parameter_info(item) for item in target.pars()[:limit]]
    return result


def _action_get_parameters(args):
    target = _operator(args["path"])
    requested = args.get("names")
    if requested:
        parameters = []
        for name in requested:
            parameter = getattr(target.par, name, None)
            if parameter is None:
                raise ValueError("Parameter does not exist: {}.par.{}".format(target.path, name))
            parameters.append(parameter)
    else:
        parameters = target.pars()
    return {"path": target.path, "parameters": [_parameter_info(item) for item in parameters]}


def _action_set_parameter(args):
    target = _operator(args["path"])
    name = args["name"]
    parameter = getattr(target.par, name, None)
    if parameter is None:
        raise ValueError("Parameter does not exist: {}.par.{}".format(target.path, name))
    if parameter.readOnly:
        raise ValueError("Parameter is read-only: {}.par.{}".format(target.path, name))
    mode = args.get("mode", "constant")
    if mode == "expression":
        parameter.expr = str(args.get("value", ""))
    else:
        parameter.val = args.get("value")
    return _parameter_info(parameter)


def _action_pulse_parameter(args):
    target = _operator(args["path"])
    parameter = getattr(target.par, args["name"], None)
    if parameter is None:
        raise ValueError("Parameter does not exist: {}.par.{}".format(target.path, args["name"]))
    parameter.pulse()
    return {"path": target.path, "parameter": parameter.name, "pulsed": True}


def _action_create_operator(args):
    parent_op = _operator(args["parent"])
    if not hasattr(parent_op, "create"):
        raise ValueError("Parent cannot contain children: {}".format(parent_op.path))
    name = args["name"]
    if parent_op.op(name) is not None:
        raise ValueError("Operator already exists: {}/{}".format(parent_op.path, name))
    target = parent_op.create(args["op_type"], name)
    if "node_x" in args:
        target.nodeX = float(args["node_x"])
    if "node_y" in args:
        target.nodeY = float(args["node_y"])
    return _operator_summary(target)


def _action_connect_operators(args):
    source = _operator(args["source"])
    target = _operator(args["target"])
    source_output = int(args.get("source_output", 0))
    target_input = int(args.get("target_input", 0))
    if source_output >= len(source.outputConnectors):
        raise ValueError("Source output index out of range")
    if target_input >= len(target.inputConnectors):
        raise ValueError("Target input index out of range")
    source.outputConnectors[source_output].connect(target.inputConnectors[target_input])
    return {"source": source.path, "source_output": source_output, "target": target.path, "target_input": target_input, "connected": True}


def _action_disconnect_input(args):
    target = _operator(args["target"])
    target_input = int(args.get("target_input", 0))
    if target_input >= len(target.inputConnectors):
        raise ValueError("Target input index out of range")
    target.inputConnectors[target_input].disconnect()
    return {"target": target.path, "target_input": target_input, "disconnected": True}


def _action_set_node_position(args):
    target = _operator(args["path"])
    target.nodeX = float(args["node_x"])
    target.nodeY = float(args["node_y"])
    return _operator_summary(target)


def _action_get_dat_text(args):
    target = _operator(args["path"])
    if not hasattr(target, "text"):
        raise ValueError("Target is not a readable text DAT: {}".format(target.path))
    max_chars = max(1, min(int(args.get("max_chars", 100000)), 2000000))
    text = target.text
    return {"path": target.path, "text": text[:max_chars], "length": len(text), "truncated": len(text) > max_chars}


def _action_set_dat_text(args):
    target = _operator(args["path"])
    if not hasattr(target, "text"):
        raise ValueError("Target is not a writable text DAT: {}".format(target.path))
    target.text = args["text"]
    return {"path": target.path, "length": len(target.text)}


def _action_destroy_operator(args):
    target = _operator(args["path"])
    if args.get("confirm") is not True:
        raise ValueError("Delete requires confirm=true")
    bridge_path = _bridge_path()
    protected = {"/", "/project1", bridge_path}
    if target.path in protected or (bridge_path and target.path.startswith(bridge_path + "/")):
        raise ValueError("Refusing to delete protected operator: {}".format(target.path))
    path = target.path
    target.destroy()
    return {"path": path, "destroyed": True}


def _action_save_project(args):
    path = args.get("path")
    if path:
        project.save(str(path))
    else:
        project.save()
    return {"saved": True, "project_name": getattr(project, "name", ""), "project_folder": getattr(project, "folder", "")}


def _action_execute_python(args):
    bridge = _bridge()
    if not bool(_par(bridge, "Allowpython").eval()):
        raise PermissionError("Arbitrary Python execution is disabled. Enable Allow Python on the bridge MCP page first.")
    namespace = {"result": None}
    exec(str(args["code"]), globals(), namespace)
    return {"result": _json_safe(namespace.get("result"))}


ACTIONS = {
    "ping": _action_ping,
    "project_info": _action_project_info,
    "list_operators": _action_list_operators,
    "operator_info": _action_operator_info,
    "get_parameters": _action_get_parameters,
    "set_parameter": _action_set_parameter,
    "pulse_parameter": _action_pulse_parameter,
    "create_operator": _action_create_operator,
    "connect_operators": _action_connect_operators,
    "disconnect_input": _action_disconnect_input,
    "set_node_position": _action_set_node_position,
    "get_dat_text": _action_get_dat_text,
    "set_dat_text": _action_set_dat_text,
    "destroy_operator": _action_destroy_operator,
    "save_project": _action_save_project,
    "execute_python": _action_execute_python,
}


def onHTTPRequest(webServerDAT, request, response):
    try:
        bridge = _set_active_bridge(webServerDAT)
        method = str(request.get("method", "GET")).upper()
        uri = str(request.get("uri", request.get("path", "/")))
        if method == "OPTIONS":
            response["Access-Control-Allow-Headers"] = "Content-Type, X-TD-MCP-Token"
            response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
            return _response(response, 204, {})
        if method != "POST" or not uri.split("?", 1)[0].endswith("/api"):
            return _response(response, 404, {"ok": False, "error": "Only POST /api is supported"})

        expected = str(_par(bridge, "Token").eval())
        supplied = _request_header(request, "x-td-mcp-token")
        if not expected or supplied != expected:
            return _response(response, 401, {"ok": False, "error": "Invalid token"})

        payload = json.loads(_request_body(request) or "{}")
        action = payload.get("action")
        args = payload.get("args") or {}
        handler = ACTIONS.get(action)
        if handler is None:
            return _response(response, 404, {"ok": False, "error": "Unknown action: {}".format(action)})
        result = handler(args)
        return _response(response, 200, {"ok": True, "result": _json_safe(result)})
    except PermissionError as error:
        return _response(response, 403, {"ok": False, "error": str(error)})
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        return _response(response, 400, {"ok": False, "error": str(error)})
    except Exception as error:
        debug("TD MCP error:\n" + traceback.format_exc())
        return _response(response, 500, {"ok": False, "error": "{}: {}".format(type(error).__name__, error)})


def onWebSocketOpen(webServerDAT, client, uri):
    return


def onWebSocketClose(webServerDAT, client):
    return


def onWebSocketReceiveText(webServerDAT, client, data):
    return


def onWebSocketReceiveBinary(webServerDAT, client, data):
    return


def onServerStart(webServerDAT):
    _set_active_bridge(webServerDAT)
    debug("TouchDesigner MCP bridge started on {}".format(webServerDAT.parent().path))
    return


def onServerStop(webServerDAT):
    _set_active_bridge(webServerDAT)
    debug("TouchDesigner MCP bridge stopped on {}".format(webServerDAT.parent().path))
    return
'''


def _existing_page(bridge, name):
    for page in bridge.customPages:
        if page.name == name:
            return page
    return None


def _custom_par(bridge, name):
    return getattr(bridge.par, name, None)


def _ensure_custom_parameters(bridge, token):
    page = _existing_page(bridge, "MCP")
    if page is None:
        page = bridge.appendCustomPage("MCP")

    if _custom_par(bridge, "Active") is None:
        par = page.appendToggle("Active", label="服务开关")[0]
        par.val = False

    if _custom_par(bridge, "Port") is None:
        par = page.appendInt("Port", label="端口")[0]
        par.val = DEFAULT_PORT
        par.normMin = 1
        par.normMax = 65535
        par.clampMin = True
        par.clampMax = True
        par.min = 1
        par.max = 65535

    if _custom_par(bridge, "Token") is None:
        par = page.appendStr("Token", label="访问令牌")[0]
        par.val = token

    if _custom_par(bridge, "Allowpython") is None:
        par = page.appendToggle("Allowpython", label="允许任意 Python")[0]
        par.val = False

    if _custom_par(bridge, "Url") is None:
        par = page.appendStr("Url", label="连接地址")[0]
        par.expr = "'http://127.0.0.1:{}/api'.format(me.par.Port.eval())"
        try:
            par.readOnly = True
        except Exception:
            pass


def install(active=True, token=None, port=DEFAULT_PORT, bridge_name="td_mcp_bridge"):
    container = op("/project1")
    if container is None:
        raise RuntimeError("Cannot find /project1")

    bridge = container.op(bridge_name) or op(BRIDGE_PATH)
    created = bridge is None
    if bridge is None:
        bridge = container.create(baseCOMP, bridge_name)
        bridge.nodeX = 0
        bridge.nodeY = -300

    if token is None:
        token = secrets.token_hex(24)

    _ensure_custom_parameters(bridge, token)
    _custom_par(bridge, "Token").val = token
    _custom_par(bridge, "Port").val = int(port)
    _custom_par(bridge, "Active").val = bool(active)
    _custom_par(bridge, "Allowpython").val = False

    callbacks = bridge.op("callbacks")
    if callbacks is None:
        callbacks = bridge.create(textDAT, "callbacks")
    callbacks.text = CALLBACKS_CODE
    callbacks.nodeX = 0
    callbacks.nodeY = 0

    webserver = bridge.op("webserver")
    if webserver is None:
        webserver = bridge.create(webserverDAT, "webserver")
    webserver.par.port.expr = "parent().par.Port"
    webserver.par.callbacks = callbacks
    webserver.par.active.expr = "parent().par.Active"
    webserver.nodeX = 180
    webserver.nodeY = 0

    bridge.comment = "TouchDesigner MCP Bridge. Open the MCP parameter page and enable 服务开关 to start."
    bridge.nodeWidth = 180
    bridge.nodeHeight = 120

    print("")
    print("TouchDesigner MCP bridge {}: {}".format("created" if created else "updated", bridge.path))
    print("URL: http://127.0.0.1:{}/api".format(_custom_par(bridge, "Port").eval()))
    print("TD_MCP_TOKEN={}".format(_custom_par(bridge, "Token").eval()))
    print("Active={}".format(_custom_par(bridge, "Active").eval()))
    return bridge


if globals().get('__name__', '__main__') == '__main__':
    install()


