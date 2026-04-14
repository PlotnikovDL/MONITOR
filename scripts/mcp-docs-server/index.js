#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import fs from "fs";
import path from "path";
import os from "os";

// Configuration - support both global and project-local standards
const PROJECT_ROOT = process.env.PROJECT_ROOT || process.cwd();
const GLOBAL_CLAUDE_DIR = path.join(os.homedir(), ".claude");

const DOCS_PATHS = [
  path.join(PROJECT_ROOT, "docs"),
];

// Document index
let documentsIndex = [];

// Load and index all documents
function indexDocuments() {
  documentsIndex = [];
  const seenPaths = new Set();

  for (const docsPath of DOCS_PATHS) {
    if (!fs.existsSync(docsPath)) continue;

    indexDirectory(docsPath, docsPath, seenPaths);
  }

  console.error(`Indexed ${documentsIndex.length} project documents from docs/`);
}

function indexDirectory(dir, baseDir, seenPaths) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      indexDirectory(fullPath, baseDir, seenPaths);
    } else if (entry.name.endsWith(".md") || entry.name.endsWith(".txt")) {
      // Skip if we've already indexed this file (by name)
      if (seenPaths.has(entry.name)) continue;
      seenPaths.add(entry.name);

      try {
        const content = fs.readFileSync(fullPath, "utf-8");
        const relativePath = path.relative(baseDir, fullPath);
        const isGlobal = fullPath.startsWith(GLOBAL_CLAUDE_DIR);

        // Extract title from first heading or filename
        const titleMatch = content.match(/^#\s+(.+)$/m);
        const title = titleMatch ? titleMatch[1] : entry.name.replace(/\.(md|txt)$/, "");

        // Extract keywords from content
        const keywords = extractKeywords(content);

        documentsIndex.push({
          path: relativePath,
          fullPath,
          title,
          keywords,
          content,
          category: getCategoryFromPath(relativePath),
          location: isGlobal ? "global" : "project",
        });
      } catch (err) {
        console.error(`Error reading ${fullPath}: ${err.message}`);
      }
    }
  }
}

function extractKeywords(content) {
  // Extract unique words, filter short ones and common words
  const words = content.toLowerCase()
    .replace(/[^\wа-яё]/gi, " ")
    .split(/\s+/)
    .filter(w => w.length > 3);

  return [...new Set(words)];
}

function getCategoryFromPath(relativePath) {
  const top = relativePath.split(/[\\/]/)[0];
  const known = {
    "v851doc": "Платформа 8.5.1",
    "bsp321doc": "БСП 3.2.1",
  };
  return known[top] || top || "docs";
}

// Search documents
function searchDocuments(query, maxResults = 10) {
  const queryWords = query.toLowerCase()
    .replace(/[^\wа-яё]/gi, " ")
    .split(/\s+/)
    .filter(w => w.length > 2);

  if (queryWords.length === 0) return [];

  const scored = documentsIndex.map(doc => {
    let score = 0;

    // Title matches (high weight)
    for (const word of queryWords) {
      if (doc.title.toLowerCase().includes(word)) score += 10;
    }

    // Keyword matches
    for (const word of queryWords) {
      const matches = doc.keywords.filter(k => k.includes(word)).length;
      score += matches;
    }

    // Content matches (check for exact phrases)
    const lowerContent = doc.content.toLowerCase();
    for (const word of queryWords) {
      const regex = new RegExp(word, "gi");
      const matches = (lowerContent.match(regex) || []).length;
      score += Math.min(matches, 5); // Cap at 5 to avoid bias toward long docs
    }

    return { ...doc, score };
  });

  return scored
    .filter(doc => doc.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, maxResults)
    .map(({ path, title, category, score, fullPath }) => ({
      path: fullPath,
      title,
      category,
      relevance: score,
    }));
}

// Read document
function readDocument(docPath) {
  const fullPath = path.isAbsolute(docPath)
    ? docPath
    : path.join(PROJECT_ROOT, "docs", docPath);

  if (!fs.existsSync(fullPath)) {
    return { error: `Document not found: ${docPath}` };
  }

  const content = fs.readFileSync(fullPath, "utf-8");
  return { content, path: docPath };
}

// List all documents
function listDocuments(category = null) {
  let docs = documentsIndex;

  if (category) {
    docs = docs.filter(d => d.category.toLowerCase().includes(category.toLowerCase()));
  }

  return docs.map(({ fullPath, title, category, location }) => ({
    path: fullPath,
    title,
    category,
    location
  }));
}

// Create MCP server
const server = new Server(
  {
    name: "project-docs-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "search",
        description: "Поиск по проектной документации в docs/ (рекурсивно, .md и .txt). Ключевые слова на русском или английском. Возвращает список релевантных документов с путями.",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "Поисковый запрос (ключевые слова, термины, фразы на русском или английском)",
            },
            maxResults: {
              type: "number",
              description: "Максимальное число результатов (по умолчанию: 10)",
            },
          },
          required: ["query"],
        },
      },
      {
        name: "read",
        description: "Получить полный текст документа из проектной базы docs/ по его пути (абсолютному или относительно docs/).",
        inputSchema: {
          type: "object",
          properties: {
            path: {
              type: "string",
              description: "Путь к документу (абсолютный или относительно docs/, например 'v851doc/002_Руководство_разработчика.txt')",
            },
          },
          required: ["path"],
        },
      },
      {
        name: "list",
        description: "Список всех проектных документов из docs/, опционально с фильтром по категории. Категории определяются динамически из имён поддиректорий docs/.",
        inputSchema: {
          type: "object",
          properties: {
            category: {
              type: "string",
              description: "Фильтр по категории (подстрока, регистронезависимо). Категории формируются из имён поддиректорий docs/.",
            },
          },
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "search": {
      const results = searchDocuments(args.query, args.maxResults || 10);
      return {
        content: [
          {
            type: "text",
            text: results.length > 0
              ? `Found ${results.length} documents:\n\n${results.map(r =>
                  `- **${r.title}** (${r.category})\n  Path: ${r.path}\n  Relevance: ${r.relevance}`
                ).join("\n\n")}`
              : "No documents found for this query.",
          },
        ],
      };
    }

    case "read": {
      const result = readDocument(args.path);
      return {
        content: [
          {
            type: "text",
            text: result.error || result.content,
          },
        ],
      };
    }

    case "list": {
      const docs = listDocuments(args.category);
      return {
        content: [
          {
            type: "text",
            text: `Available documents (${docs.length}):\n\n${docs.map(d =>
              `- **${d.title}** [${d.category}]\n  ${d.path}`
            ).join("\n")}`,
          },
        ],
      };
    }

    default:
      return {
        content: [{ type: "text", text: `Unknown tool: ${name}` }],
        isError: true,
      };
  }
});

// Start server
async function main() {
  indexDocuments();

  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error("MCP Project Docs Server started (project mode)");
}

main().catch(console.error);
