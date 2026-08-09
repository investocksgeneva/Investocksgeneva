import { useCallback, useEffect, useState } from 'react'

type ProgressState = {
  completedSessions: Record<string, boolean>
  knownVocab: Record<string, boolean>
}

const STORAGE_KEY = 'geneva-french-progress'

function loadState(): ProgressState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { completedSessions: {}, knownVocab: {} }
    const parsed = JSON.parse(raw)
    return {
      completedSessions: parsed.completedSessions ?? {},
      knownVocab: parsed.knownVocab ?? {},
    }
  } catch {
    return { completedSessions: {}, knownVocab: {} }
  }
}

export function useProgress() {
  const [state, setState] = useState<ProgressState>(loadState)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  }, [state])

  const isSessionComplete = useCallback(
    (weekId: number, sessionId: number) =>
      Boolean(state.completedSessions[`${weekId}-${sessionId}`]),
    [state.completedSessions],
  )

  const setSessionComplete = useCallback(
    (weekId: number, sessionId: number, complete: boolean) => {
      setState((prev) => ({
        ...prev,
        completedSessions: {
          ...prev.completedSessions,
          [`${weekId}-${sessionId}`]: complete,
        },
      }))
    },
    [],
  )

  const isVocabKnown = useCallback(
    (fr: string) => Boolean(state.knownVocab[fr]),
    [state.knownVocab],
  )

  const setVocabKnown = useCallback((fr: string, known: boolean) => {
    setState((prev) => ({
      ...prev,
      knownVocab: { ...prev.knownVocab, [fr]: known },
    }))
  }, [])

  return {
    isSessionComplete,
    setSessionComplete,
    isVocabKnown,
    setVocabKnown,
    knownVocabCount: Object.values(state.knownVocab).filter(Boolean).length,
    completedSessionsCount: Object.values(state.completedSessions).filter(Boolean)
      .length,
  }
}
