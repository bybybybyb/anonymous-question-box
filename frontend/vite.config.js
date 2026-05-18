import vue from "@vitejs/plugin-vue";

const apiTarget = process.env.AQBOX_API_TARGET || "http://localhost:3768";

module.exports = {
  server: {
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  plugins: [vue()],
};
