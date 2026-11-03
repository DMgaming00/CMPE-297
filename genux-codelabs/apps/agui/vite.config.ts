import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import { aguiApi } from "./server/api";

export default defineConfig(({ mode }) => ({ plugins: [react(), aguiApi(loadEnv(mode, process.cwd(), ""))] }));
