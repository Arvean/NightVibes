// This file explicitly defines Jest globals
// It gets loaded first in the jest.config.js setupFiles array

const jestGlobals = require('@jest/globals');

// Make Jest globals available in the global scope
global.jest = jestGlobals.jest;
global.describe = jestGlobals.describe;
global.beforeAll = jestGlobals.beforeAll;
global.afterAll = jestGlobals.afterAll;
global.beforeEach = jestGlobals.beforeEach;
global.afterEach = jestGlobals.afterEach;
global.it = jestGlobals.it;
global.test = jestGlobals.test;
global.expect = jestGlobals.expect;

// Also define __DEV__ for React Native
global.__DEV__ = true;

console.log('Jest globals setup completed');