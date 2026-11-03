import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { a2uiApi } from "./server/api";

export default defineConfig({ plugins: [react(), a2uiApi()] });
