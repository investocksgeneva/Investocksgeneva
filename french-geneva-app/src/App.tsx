import { useState } from 'react'
import { weeks } from './data/curriculum'
import { BottomNav, type Tab } from './components/BottomNav'
import { TopBar } from './components/TopBar'
import { WeekSwitcher } from './components/WeekSwitcher'
import { HomeScreen } from './screens/HomeScreen'
import { SessionScreen } from './screens/SessionScreen'
import { VocabScreen } from './screens/VocabScreen'
import { ProgressScreen } from './screens/ProgressScreen'
import './App.css'

function App() {
  const [tab, setTab] = useState<Tab>('home')
  const [weekId, setWeekId] = useState(weeks[0].id)
  const [openSessionId, setOpenSessionId] = useState<number | null>(null)

  const activeWeek = weeks.find((w) => w.id === weekId) ?? weeks[0]

  const openSession = openSessionId
    ? activeWeek.sessions.find((s) => s.id === openSessionId) ?? null
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
      {!openSession && (
        <WeekSwitcher
          weeks={weeks}
          activeWeekId={weekId}
          onChange={(id) => {
            setWeekId(id)
            setOpenSessionId(null)
          }}
        />
      )}
      <main className="app-content">
        {tab === 'home' &&
          (openSession ? (
            <SessionScreen weekId={activeWeek.id} session={openSession} />
          ) : (
            <HomeScreen week={activeWeek} onOpenSession={setOpenSessionId} />
          ))}
        {tab === 'vocab' && <VocabScreen vocab={activeWeek.vocab} />}
        {tab === 'progress' && <ProgressScreen week={activeWeek} />}
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
