import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import { harnessApi } from "./server/api";

export default defineConfig(({ mode }) => ({ plugins: [react(), harnessApi(loadEnv(mode, process.cwd(), ""))] }));
