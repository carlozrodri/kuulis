// Lucide icons ship as ES modules; component tests only need something to render.
const { View } = require('react-native');
const React = require('react');

function Icon(props) {
  return React.createElement(View, { testID: props.testID });
}
module.exports = Icon;
module.exports.default = Icon;
