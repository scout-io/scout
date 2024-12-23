const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
    app.use(
        '/api',
        createProxyMiddleware({
            target: 'http://127.0.0.1:8000',
            changeOrigin: true,
            pathRewrite: {
                '^/api': '', // remove "/api" from the forwarded URL
            },
        })
    );

    app.use(
        '/logs/stream',
        createProxyMiddleware({
            target: 'http://127.0.0.1:8000',
            changeOrigin: true,
        })
    );
};
