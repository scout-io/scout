const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
    app.use(
        '/api',
        createProxyMiddleware({
            target: 'http://127.0.0.1:8000',
            changeOrigin: true,
        })
    );

    app.use(
        '/logs/stream',
        createProxyMiddleware({
            target: 'http://127.0.0.1:8000',
            changeOrigin: true,
        })
    );

    app.use(
        '/admin',
        createProxyMiddleware({
            target: 'http://127.0.0.1:8000',
            changeOrigin: true,
        })
    );

    app.use(
        '/openapi',
        createProxyMiddleware({
            target: 'http://127.0.0.1:8000/openapi.json',
            changeOrigin: true,
            pathRewrite: {
                '^/openapi': '',
            },
        })
    );
};
