import { useState } from 'react';
import { StateProvider, useApp } from './state';
import { Onboarding } from './components/Onboarding';
import { AlbumView } from './components/AlbumView';
import { TradesView } from './components/TradesView';
import { ForecastView } from './components/ForecastView';
import { ProfileView } from './components/ProfileView';
import { Logo } from './components/Logo';
import { AlbumIcon, TradeIcon, ForecastIcon, ProfileIcon, SunIcon, MoonIcon } from './components/Icons';

type View = 'album' | 'trades' | 'forecast' | 'profile';

const NAV: { id: View; label: string; Icon: React.FC<{ size?: number }> }[] = [
  { id: 'album', label: 'Album', Icon: AlbumIcon },
  { id: 'trades', label: 'Trades', Icon: TradeIcon },
  { id: 'forecast', label: 'Forecast', Icon: ForecastIcon },
  { id: 'profile', label: 'Profile', Icon: ProfileIcon },
];

function Shell() {
  const { profile, resolvedTheme, setTheme, theme } = useApp();
  const [view, setView] = useState<View>('album');

  if (!profile) return <Onboarding />;

  const toggleTheme = () => {
    // Cycle system -> light -> dark -> system
    if (theme === 'system') setTheme('light');
    else if (theme === 'light') setTheme('dark');
    else setTheme('system');
  };

  return (
    <div className="app">
      <header className="header">
        <div className="shell header-row">
          <span className="brand" style={{ color: 'var(--accent)' }}>
            <Logo size={28} />
            <span style={{ color: 'var(--text)' }}>Estádio</span>
            <span className="brand-tag hidden-mobile">WC 2026 album</span>
          </span>
          <nav className="tabs" role="tablist" aria-label="Primary">
            {NAV.map(n => (
              <button key={n.id} className="tab" aria-current={view === n.id ? 'page' : undefined} onClick={() => setView(n.id)}>
                {n.label}
              </button>
            ))}
          </nav>
          <span className="spacer" />
          <button className="icon-btn" onClick={toggleTheme} aria-label={`Theme: ${theme}. Click to cycle.`} title={`Theme: ${theme}`}>
            {resolvedTheme === 'dark' ? <MoonIcon /> : <SunIcon />}
          </button>
          <span className="user-pill">
            <span className="avatar">{profile.alias.split(' ').map(s => s[0]).slice(0,2).join('').toUpperCase() || 'U'}</span>
            <span className="who">{profile.alias.split(' ')[0]}</span>
          </span>
        </div>
      </header>

      <main className="shell" style={{ paddingTop: 18, paddingBottom: 32 }}>
        {view === 'album' && <AlbumView />}
        {view === 'trades' && <TradesView />}
        {view === 'forecast' && <ForecastView />}
        {view === 'profile' && <ProfileView />}
      </main>

      <nav className="mobile-tabs" aria-label="Primary (mobile)">
        {NAV.map(n => (
          <button key={n.id} className="mobile-tab" aria-current={view === n.id ? 'page' : undefined} onClick={() => setView(n.id)}>
            <n.Icon />
            {n.label}
          </button>
        ))}
      </nav>

      <footer className="foot">
        Estádio · sample catalog of {1041} stickers. Not affiliated with FIFA or Panini. Replace <code>src/data/catalog.json</code> with the official checklist.
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <StateProvider>
      <Shell />
    </StateProvider>
  );
}
