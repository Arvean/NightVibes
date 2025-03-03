// Mock implementation of Platform
module.exports = {
  OS: 'ios',
  select: obj => obj.ios || obj.default || {},
  Version: 10,
  isTesting: true,
  isPad: false,
  isTV: false
}; 