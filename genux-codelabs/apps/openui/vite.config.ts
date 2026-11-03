import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { openuiApi } from "./server/api";

export default defineConfig({ plugins: [react(), openuiApi()] });
