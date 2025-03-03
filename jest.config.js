module.exports = {
  preset: 'react-native',
  
  // Map module imports to mocks
  moduleNameMapper: {
    '^react-native$': '<rootDir>/node_modules/react-native',
    '^react-native/(.*)': '<rootDir>/node_modules/react-native/$1'
  },
  
  // Include all file extensions
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json', 'node'],
  
  // Setup files
  setupFiles: ['<rootDir>/src/setupTests.js'],
  
  // Ignore transforming node_modules except for specific packages
  transformIgnorePatterns: [
    'node_modules/(?!(react-native|@react-native|@react-navigation|react-navigation|@react-native-community)/)'
  ],
  
  // Enable mocking for node modules
  modulePathIgnorePatterns: [],
  
  // Use a faster test environment
  testEnvironment: 'node',
  
  // Clear mocks between tests
  clearMocks: true
}; 