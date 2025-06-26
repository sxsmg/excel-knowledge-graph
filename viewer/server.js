import express          from "express";
import path, { dirname } from "path";
import { fileURLToPath } from "url";
import * as dotenv       from "dotenv";
dotenv.config();

const __dirname = dirname(fileURLToPath(import.meta.url));
const app        = express();

/* serve /public as the site root  ───────────────────────────── */
app.use(express.static(path.join(__dirname, "public")));

/* full UMD bundle (includes vis-network) */
app.get("/neovis.js", (_req, res) =>
  res.sendFile(
    path.join(__dirname,
      "node_modules/neovis.js/dist/neovis.js")
  )
);

/* Neo4j creds for the browser  ──────────────────────────────── */
app.get("/config", (_req, res) => {
  res.json({
    uri      : process.env.NEO4J_URI      ?? "bolt://localhost:7687",
    user     : process.env.NEO4J_USER     ?? "neo4j",
    password : process.env.NEO4J_PASSWORD ?? "password"
  });
});
// viewer/server.js
app.get("/vis-network.min.js", (_req, res) => {
  res.sendFile(
    path.join(
      __dirname,
      "node_modules/vis-network/standalone/umd/vis-network.min.js"
    )
  );
});

app.listen(3000, () =>
  console.log("🚀  Graph viewer running → http://localhost:3000")
);
