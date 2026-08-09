import { useCallback, useEffect, useState } from 'react'

export function useSpeech() {
  const [supported, setSupported] = useState(false)

  useEffect(() => {
    setSupported(typeof window !== 'undefined' && 'speechSynthesis' in window)
  }, [])

  const speak = useCallback(
    (text: string) => {
      if (!supported) return
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = 'fr-FR'
      utterance.rate = 0.9
      window.speechSynthesis.speak(utterance)
    },
    [supported],
  )

  return { speak, supported }
}
