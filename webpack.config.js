const path = require('path');
const webpack = require('webpack');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const CssMinimizerPlugin = require('css-minimizer-webpack-plugin');
const MomentLocalesPlugin = require('moment-locales-webpack-plugin');
const GoogleFontsPlugin = require("@beyonk/google-fonts-webpack-plugin");

module.exports = {
  entry: {
    'main': './frontend/index.ts',
    'datatables': {
      'import': './frontend/datatables.ts',
      'dependOn': 'main',
    },
    'tinymce': {
      'import': './frontend/tinymce.ts',
      'dependOn': 'main',
    },
  },
  output: {
    filename: '[name].js',
    path: path.resolve(__dirname, './static/dist'),
  },
  devServer: {
    writeToDisk: true, // Write files to disk in dev mode, so Django can serve the assets
    hot: true
  },
  module: {
    rules: [
      {
        test: /\.css$/,
        use: [
          MiniCssExtractPlugin.loader,
          'css-loader'
        ]
      },
      { test: /\.(png|woff|woff2|eot|ttf|svg)$/, loader: 'url-loader' },
      {
        test: require.resolve("jquery"),
        loader: "expose-loader",
        options: {
          exposes: ["$", "jQuery"],
        },
      },
    ],
  },
  resolve: {
    alias: {
      // Force all modules to use the same jquery version
      // (because eonasdan-bootstrap-datetimepicker-npm is broken)
      // Thanks to https://medium.com/mitchtalmadge/datetimepicker-is-not-a-function-webpack-fix-551177a11035 for the fix
      'jquery': path.join(__dirname, 'node_modules/jquery/src/jquery')
    },
  },
  plugins: [
    new MiniCssExtractPlugin(),
    new GoogleFontsPlugin({
      fonts: [
        { family: "Open Sans", variants: [ "300", "400", "700" ], display: "swap", subsets: ["latin-ext"] }
      ]
    }),
    new MomentLocalesPlugin({
          localesToKeep: ['pl'],
    }),
    new webpack.ProvidePlugin({
      jQuery: 'jquery',
      $: 'jquery',
      moment: 'moment',
    }),
  ],
  optimization: {
    minimizer: [
      `...`,
      new CssMinimizerPlugin(),
    ],
  },
};