import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  cpSync,
  rmSync,
  existsSync,
} from "node:fs";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../", import.meta.url));
rmSync(root + "dist", { recursive: true, force: true });
mkdirSync(root + "dist/server", { recursive: true });
mkdirSync(root + "dist/.openai", { recursive: true });
const names = {
  "/": "index.html",
  "/.well-known/agentix.json": "agentix.json",
  "/llms.txt": "llms.txt",
  "/assets/app.js": "app.js",
  "/assets/style.css": "style.css",
};
const webRoot = existsSync(root + "../src/agentix/web")
  ? root + "../src/agentix/web/"
  : root + "web/";
const assets = Object.fromEntries(
  Object.entries(names).map(([route, file]) => [
    route,
    readFileSync(webRoot + file, "utf8"),
  ]),
);
const service = readFileSync(root + "worker/service.js", "utf8");
writeFileSync(
  root + "dist/server/index.js",
  service +
    "\nconst assets=" +
    JSON.stringify(assets) +
    ';\nexport default {async fetch(request,env){const path=new URL(request.url).pathname;if(path.startsWith("/v1/")||path.startsWith("/health/"))return service(request,env);const route=["/creator","/agent","/superadmin"].includes(path)?"/":path;const body=assets[route];if(body===undefined)return new Response("Not found",{status:404});return new Response(body,{headers:{"Content-Type":path.endsWith(".json")?"application/json":path.endsWith(".txt")?"text/plain; charset=utf-8":path.endsWith(".js")?"application/javascript":path.endsWith(".css")?"text/css":"text/html", "X-Content-Type-Options":"nosniff","Cache-Control":"no-store"}});}};\n',
);
cpSync(root + ".openai/hosting.json", root + "dist/.openai/hosting.json");
cpSync(root + "drizzle", root + "dist/drizzle", { recursive: true });
console.log("Built hosted/dist");
