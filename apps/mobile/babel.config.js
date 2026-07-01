module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
    // Reanimated 4 moved its worklets Babel plugin into react-native-worklets.
    plugins: ["react-native-worklets/plugin"],
  };
};
