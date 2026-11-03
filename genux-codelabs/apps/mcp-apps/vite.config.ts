import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { mcpHostApi } from "./server/api";

export default defineConfig({ plugins: [react(), mcpHostApi()] });
