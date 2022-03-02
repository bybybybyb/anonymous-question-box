import vue from "@vitejs/plugin-vue";
module.exports = {
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:3768",
        changeOrigin: true,
        secure: false,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  plugins: [vue()],
};
