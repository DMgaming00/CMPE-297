import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { mixedApi } from "./server/api";

export default defineConfig({ plugins: [react(), mixedApi()] });
