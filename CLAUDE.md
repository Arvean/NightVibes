# NightVibes Development Guide

## Build Commands
- Frontend: `npm start`, `npm run android`, `npm run ios`
- Backend: `docker-compose up`, `docker-compose down`
- Database: `docker-compose exec web python manage.py migrate`

## Test Commands
- All tests: `npm test` (frontend), `python manage.py test` (backend)
- Single test: `npx jest path/to/test.js -t "test name"`
- Coverage: `npm test` (reports in coverage/)
- Run specific tests: `npx jest AuthContext.test.js ThemeContext.test.js`

## Lint/Format
- Frontend: `npm run lint`

## Code Style
- **Frontend**: React functional components with hooks
- **Naming**: PascalCase for components, camelCase for functions/variables
- **Imports**: Group by external packages, then internal components
- **Error handling**: Try/catch with user-friendly alerts
- **Components**: State at top, useEffect hooks together, helpers at end
- **Styling**: StyleSheet API with descriptive names

## Testing Guidelines
- Mock the `axiosInstance` for API calls using the global mock
- Use `renderWithProviders` for component tests with proper context
- Mock contexts (AuthContext, ThemeContext) directly from __mocks__ folder
- Avoid directly importing components that require UI modules like 'card'
- Fix navigation test errors by properly mocking useNavigation hook
- For challenging components, start with simple tests like rendering empty components
- Always wrap async operations with `act()` to handle React state updates
- When testing navigation, use `jest.mock('@react-navigation/native')` with proper implementation
- Use `await act(async () => { component = renderWithProviders(<Component />) })` pattern for components
- Check TESTING-FIXES.md and src/__tests__/README.md for detailed guides on fixing test issues

## Important Rules
- MAKE ONLY THE MINIMUM CHANGES REQUIRED TO ACCOMPLISH YOUR TASK
- DO NOT MAKE IMPROVEMENTS OR REFACTORING UNLESS EXPLICITLY REQUESTED