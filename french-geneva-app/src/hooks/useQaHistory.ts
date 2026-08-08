import { useCallback, useEffect, useState } from 'react'

export type QaExchange = {
  id: string
  question: string
  answerIds: string[]
}

const STORAGE_KEY = 'geneva-french-qa-history'

function loadHistory(): QaExchange[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function useQaHistory() {
  const [history, setHistory] = useState<QaExchange[]>(loadHistory)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history))
  }, [history])

  const addExchange = useCallback((question: string, answerIds: string[]) => {
    setHistory((prev) => [
      ...prev,
      { id: `${Date.now()}-${Math.random()}`, question, answerIds },
    ])
  }, [])

  const clearHistory = useCallback(() => setHistory([]), [])

  return { history, addExchange, clearHistory }
}
