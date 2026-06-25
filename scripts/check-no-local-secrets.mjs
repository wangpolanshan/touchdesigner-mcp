import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const forbiddenPatterns = [
  { name: 'Windows user profile path', pattern: /C:\\Users\\/i },
  { name: 'workspace path', pattern: /Documents\\Codex/i },
  { name: 'local user name', pattern: /POLAN/i },
  { name: 'desktop temp/app path', pattern: /AppData|Desktop/i },
  { name: 'known local proxy', pattern: /127\.0\.0\.1:10090/ },
  { name: 'known runtime token prefix', pattern: /b41ac5c47/i },
  { name: 'personal email sample', pattern: /pzy3599457899|163\.com/i },
  { name: 'test project Chinese filename', pattern: /测试/ },
];

const ignoredDirs = new Set(['.git', 'node_modules', 'dist', 'dist-test', 'work', '__pycache__']);
const ignoredFiles = [
  /\.zip$/i,
  /\.pyc$/i,
  /\.bkp\d*$/i,
  /\.toc$/i,
  /before-.*\.tox$/i,
  /touchdesigner[\\/]install_td_mcp_deployed\.py$/i,
  /scripts[\\/]check-no-local-secrets\.mjs$/i,
];
const roots = ['src', 'test', 'touchdesigner', 'scripts', '.github', 'outputs'];
const rootFiles = ['README.md', 'package.json', 'package-lock.json', 'tsconfig.json', 'tsconfig.test.json', '.env.example', '.gitignore'];

function collectFiles(path, out) {
  const stat = statSync(path);
  if (stat.isDirectory()) {
    const base = path.split(/[\\/]/).pop();
    if (ignoredDirs.has(base) || path.endsWith('.tox.dir')) return;
    for (const entry of readdirSync(path)) collectFiles(join(path, entry), out);
    return;
  }
  if (ignoredFiles.some((pattern) => pattern.test(path))) return;
  out.push(path);
}

const files = [];
for (const file of rootFiles) collectFiles(file, files);
for (const root of roots) {
  try { collectFiles(root, files); } catch {}
}

const failures = [];
for (const path of files) {
  let text;
  try {
    text = readFileSync(path, 'utf8');
  } catch {
    continue;
  }
  for (const { name, pattern } of forbiddenPatterns) {
    if (pattern.test(text)) failures.push(`${relative(process.cwd(), path)}: contains ${name}`);
  }
}

if (failures.length) {
  console.error('Local information / secret check failed:');
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log(`Local information / secret check passed for ${files.length} files.`);
