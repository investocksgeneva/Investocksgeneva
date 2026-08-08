import type { DialogueLine } from '../data/curriculum'
import { SpeakButton } from './SpeakButton'

export function DialogueView({ lines }: { lines: DialogueLine[] }) {
  return (
    <div className="dialogue">
      {lines.map((line, i) => (
        <div key={i} className={`dialogue-line side-${line.speaker === 'A' ? 'left' : 'right'}`}>
          <div className="dialogue-bubble">
            <p className="dialogue-fr">{line.fr}</p>
            <p className="dialogue-en">{line.en}</p>
          </div>
          <SpeakButton text={line.fr} />
        </div>
      ))}
    </div>
  )
}
