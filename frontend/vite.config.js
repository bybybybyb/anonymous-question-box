module.exports = {
  proxy: {
    '/api': {
      target: 'http://localhost:3768',
      changeOrigin: true,
      secure: false,
      ws: true,
      rewrite: path => path.replace(/^\/api/, '')
    }
  },
}
