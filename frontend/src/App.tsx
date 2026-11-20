import { AppShell } from './app/AppShell';
import { AppProviders } from './app/providers/AppProviders';

export function App() {
  return (
    <AppProviders>
      <AppShell />
    </AppProviders>
  );
}

export default App;
