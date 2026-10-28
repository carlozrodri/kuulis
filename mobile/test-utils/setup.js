// Native modules that jest-expo does not mock (component tests).
jest.mock('@react-native-community/netinfo', () => require('@react-native-community/netinfo/jest/netinfo-mock.js'));

// Gestures (draggable map sheet) render as plain views in tests.
require('react-native-gesture-handler/jestSetup');
// Gesture Handler installs bindings into the Worklets UI runtime, which does not exist under Jest.
jest.mock('react-native-worklets', () => ({ ...jest.requireActual('react-native-worklets'), getUIRuntimeHolder: undefined }));
