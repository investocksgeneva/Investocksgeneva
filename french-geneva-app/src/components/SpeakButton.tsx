import { useSpeech } from '../hooks/useSpeech'

export function SpeakButton({ text }: { text: string }) {
  const { speak, supported } = useSpeech()
  if (!supported) return null
  return (
    <button
      type="button"
      className="speak-btn"
      aria-label={`Listen to "${text}"`}
      onClick={() => speak(text)}
    >
      🔊
    </button>
  )
}
