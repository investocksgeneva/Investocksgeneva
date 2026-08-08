import { useState } from 'react'
import { week1 } from './data/curriculum'
import { BottomNav, type Tab } from './components/BottomNav'
import { TopBar } from './components/TopBar'
import { HomeScreen } from './screens/HomeScreen'
import { SessionScreen } from './screens/SessionScreen'
import { VocabScreen } from './screens/VocabScreen'
import { ProgressScreen } from './screens/ProgressScreen'
import './App.css'

function App() {
  const [tab, setTab] = useState<Tab>('home')
  const [openSessionId, setOpenSessionId] = useState<number | null>(null)

  const openSession = openSessionId
    ? week1.sessions.find((s) => s.id === openSessionId) ?? null
    : null

  const titleForTab: Record<Tab, string> = {
    home: 'Français — Genève',
    vocab: 'Vocabulary',
    progress: 'Progress',
  }

  const title = openSession ? openSession.title : titleForTab[tab]

  return (
    <div className="app-shell">
      <TopBar
        title={title}
        onBack={openSession ? () => setOpenSessionId(null) : undefined}
      />
      <main className="app-content">
        {tab === 'home' &&
          (openSession ? (
            <SessionScreen weekId={week1.id} session={openSession} />
          ) : (
            <HomeScreen week={week1} onOpenSession={setOpenSessionId} />
          ))}
        {tab === 'vocab' && <VocabScreen vocab={week1.vocab} />}
        {tab === 'progress' && <ProgressScreen week={week1} />}
      </main>
      <BottomNav
        active={tab}
        onChange={(next) => {
          setOpenSessionId(null)
          setTab(next)
        }}
      />
    </div>
  )
}

export default App
