export type Phrase = {
  fr: string
  en: string
  note?: string
}

export type DialogueLine = {
  speaker: string
  fr: string
  en: string
}

export type UseCase = {
  phrase: string
  use: string
}

export type NumberEntry = {
  n: number
  fr: string
  swissTwist?: string
}

export type Session = {
  id: number
  title: string
  subtitle: string
  kind: 'phrases' | 'numbers' | 'transaction' | 'roleplay'
  corePhrases?: Phrase[]
  grammarSeed?: string
  dialogue?: DialogueLine[]
  drill: string
  numbers?: NumberEntry[]
  numbersUseCase?: string
  useCases?: UseCase[]
  roleplaySteps?: { title: string; hint: string }[]
}

export type VocabItem = {
  fr: string
  en: string
}

export type Week = {
  id: number
  title: string
  goal: string
  sessions: Session[]
  vocab: VocabItem[]
}

const numbers: NumberEntry[] = [
  { n: 0, fr: 'zéro' },
  { n: 1, fr: 'un' },
  { n: 2, fr: 'deux' },
  { n: 3, fr: 'trois' },
  { n: 4, fr: 'quatre' },
  { n: 5, fr: 'cinq' },
  { n: 6, fr: 'six' },
  { n: 7, fr: 'sept' },
  { n: 8, fr: 'huit' },
  { n: 9, fr: 'neuf' },
  { n: 10, fr: 'dix' },
  { n: 11, fr: 'onze' },
  { n: 12, fr: 'douze' },
  { n: 13, fr: 'treize' },
  { n: 14, fr: 'quatorze' },
  { n: 15, fr: 'quinze' },
  { n: 16, fr: 'seize' },
  { n: 17, fr: 'dix-sept' },
  { n: 18, fr: 'dix-huit' },
  { n: 19, fr: 'dix-neuf' },
  { n: 20, fr: 'vingt' },
  { n: 30, fr: 'trente' },
  { n: 40, fr: 'quarante' },
  { n: 50, fr: 'cinquante' },
  { n: 60, fr: 'soixante' },
  {
    n: 70,
    fr: 'septante',
    swissTwist:
      'France says "soixante-dix" (60+10). Swiss French always says septante — much simpler.',
  },
  {
    n: 80,
    fr: 'huitante',
    swissTwist:
      'Some Swiss regions say "huitante" or "octante", but Geneva often still uses the French "quatre-vingts" (4×20). Listen for both.',
  },
  {
    n: 90,
    fr: 'nonante',
    swissTwist:
      'France says "quatre-vingt-dix" (4×20+10). Swiss French always says nonante — the single biggest trap for France-focused apps.',
  },
  { n: 100, fr: 'cent' },
]

export const week1: Week = {
  id: 1,
  title: 'Week 1: Foundations',
  goal:
    'Survive a 30-second transactional exchange (greeting → request → thanks → goodbye) without freezing.',
  sessions: [
    {
      id: 1,
      title: 'Bonjour to Au revoir',
      subtitle: 'Greetings & courtesy',
      kind: 'phrases',
      corePhrases: [
        { fr: 'Bonjour', en: 'Hello / Good day' },
        { fr: 'Bonsoir', en: 'Good evening' },
        { fr: "Je m'appelle…", en: 'My name is…' },
        { fr: 'Comment allez-vous ?', en: 'How are you?' },
        { fr: 'Très bien, merci', en: 'Very well, thank you' },
        { fr: "S'il vous plaît", en: 'Please' },
        { fr: 'Merci', en: 'Thank you' },
        { fr: 'De rien', en: "You're welcome" },
        { fr: 'Au revoir', en: 'Goodbye' },
        { fr: 'Bonne journée', en: 'Have a good day' },
      ],
      grammarSeed:
        '"Vous" is the Swiss social default — skip "tu" entirely for now; you\'ll almost never need it in Geneva transactional settings.',
      dialogue: [
        { speaker: 'A', fr: 'Bonjour Madame.', en: 'Hello Madam.' },
        {
          speaker: 'B',
          fr: 'Bonjour Monsieur, comment allez-vous ?',
          en: 'Hello Sir, how are you?',
        },
        {
          speaker: 'A',
          fr: 'Très bien, merci, et vous ?',
          en: 'Very well, thank you, and you?',
        },
        { speaker: 'B', fr: 'Ça va bien, merci.', en: "I'm doing well, thanks." },
      ],
      drill: 'Say it out loud 5x, varying the time of day (bonjour / bonsoir).',
    },
    {
      id: 2,
      title: 'Numbers & the Swiss twist',
      subtitle: '0–100, Geneva-style',
      kind: 'numbers',
      numbers,
      numbersUseCase:
        'Use case: prices, addresses, phone numbers, bus lines.',
      drill: 'Read your own address and phone number aloud in French.',
    },
    {
      id: 3,
      title: 'First transaction',
      subtitle: 'Boulangerie / kiosk',
      kind: 'transaction',
      useCases: [
        { phrase: 'Je voudrais…', use: '"I would like…" (softer than "je veux")' },
        { phrase: 'Un / une…, s\'il vous plaît', use: 'ordering' },
        { phrase: "C'est combien ?", use: 'asking price' },
        { phrase: 'Voilà', use: 'handing something over' },
        { phrase: 'Avez-vous… ?', use: '"do you have…?"' },
      ],
      dialogue: [
        {
          speaker: 'A',
          fr: 'Bonjour, je voudrais un café, s\'il vous plaît.',
          en: 'Hello, I would like a coffee, please.',
        },
        {
          speaker: 'B',
          fr: 'Voilà, ça fait trois francs cinquante.',
          en: "Here you go, that's three francs fifty.",
        },
        { speaker: 'A', fr: 'Merci, au revoir !', en: 'Thank you, goodbye!' },
      ],
      drill: 'Practice ordering three different items using "Je voudrais…, s\'il vous plaît."',
    },
    {
      id: 4,
      title: 'Consolidation & role-play',
      subtitle: 'Checkpoint',
      kind: 'roleplay',
      drill:
        'Combine Sessions 1–3 into one unscripted role-play. This is your checkpoint — if you can do this cold, Week 1 is done.',
      roleplaySteps: [
        { title: 'Enter and greet', hint: 'Bonjour Madame / Monsieur.' },
        {
          title: 'Ask for an item',
          hint: 'Je voudrais…, s\'il vous plaît.',
        },
        { title: 'Ask the price', hint: "C'est combien ?" },
        { title: 'Pay and hand it over', hint: 'Voilà.' },
        { title: 'Thank and leave', hint: 'Merci, au revoir ! Bonne journée !' },
      ],
    },
  ],
  vocab: [
    { fr: 'bonjour', en: 'hello / good day' },
    { fr: 'bonsoir', en: 'good evening' },
    { fr: 'merci', en: 'thank you' },
    { fr: "s'il vous plaît", en: 'please' },
    { fr: 'voilà', en: 'here you go / there it is' },
    { fr: 'combien', en: 'how much' },
    { fr: 'franc', en: 'franc (currency)' },
    { fr: 'centime', en: 'centime (currency)' },
    { fr: 'je voudrais', en: 'I would like' },
    { fr: 'avez-vous', en: 'do you have' },
    { fr: 'oui', en: 'yes' },
    { fr: 'non', en: 'no' },
    { fr: 'pardon', en: 'sorry / pardon' },
    { fr: 'excusez-moi', en: 'excuse me' },
    { fr: 'dix', en: 'ten' },
    { fr: 'vingt', en: 'twenty' },
    { fr: 'trente', en: 'thirty' },
    { fr: 'septante', en: 'seventy (Swiss)' },
    { fr: 'nonante', en: 'ninety (Swiss)' },
    { fr: 'cent', en: 'one hundred' },
  ],
}

export const week2: Week = {
  id: 2,
  title: 'Week 2: Getting around',
  goal:
    'Get from your front door to a tram stop, buy a ticket, ride, and get off at the right stop — entirely in French.',
  sessions: [
    {
      id: 1,
      title: 'Asking for directions',
      subtitle: 'Où est... ?',
      kind: 'phrases',
      corePhrases: [
        { fr: 'Excusez-moi', en: 'Excuse me' },
        { fr: 'Où est... ?', en: 'Where is... ?' },
        { fr: 'Où se trouve... ?', en: 'Where is... located?' },
        { fr: "C'est loin ?", en: 'Is it far?' },
        { fr: "C'est près d'ici", en: "It's close by" },
        { fr: 'Tout droit', en: 'Straight ahead' },
        { fr: 'À gauche', en: 'To the left' },
        { fr: 'À droite', en: 'To the right' },
        { fr: 'Au coin de', en: 'At the corner of' },
        { fr: 'En face de', en: 'Across from' },
      ],
      grammarSeed:
        '"Excusez-moi" always opens a direction question in Geneva — it signals politeness before interrupting a stranger. Pair it with "vous", same as always.',
      dialogue: [
        {
          speaker: 'A',
          fr: "Excusez-moi, où est l'arrêt de tram le plus proche ?",
          en: "Excuse me, where's the nearest tram stop?",
        },
        {
          speaker: 'B',
          fr: 'C\'est tout droit, à cinq minutes à pied.',
          en: "It's straight ahead, a five-minute walk.",
        },
        { speaker: 'A', fr: 'Merci beaucoup !', en: 'Thank you very much!' },
        { speaker: 'B', fr: 'Je vous en prie.', en: "You're welcome." },
      ],
      drill:
        'Ask for directions to three different places out loud: la gare, une pharmacie, un arrêt de bus.',
    },
    {
      id: 2,
      title: 'TPG & tickets',
      subtitle: 'Buying your way onto the tram',
      kind: 'transaction',
      grammarSeed:
        "Geneva's entire public transport network — bus, tram, and trains within the city — runs under one brand: unireso. One ticket covers all of it, so you never need to specify bus vs. tram when buying.",
      useCases: [
        { phrase: 'Un billet pour…, s\'il vous plaît.', use: 'buying a ticket' },
        { phrase: 'C\'est quelle ligne pour… ?', use: 'asking which line goes somewhere' },
        {
          phrase: 'Le prochain bus/tram, c\'est à quelle heure ?',
          use: 'asking the next departure time',
        },
        { phrase: 'Ça s\'arrête où ?', use: 'asking where it stops' },
        { phrase: 'C\'est direct ou il faut changer ?', use: 'asking about transfers' },
      ],
      dialogue: [
        {
          speaker: 'A',
          fr: 'Bonjour, un billet pour Cornavin, s\'il vous plaît.',
          en: 'Hello, one ticket to Cornavin, please.',
        },
        {
          speaker: 'B',
          fr: 'Voilà, c\'est le tram 15, quai B.',
          en: "Here you go, it's tram 15, platform B.",
        },
        { speaker: 'A', fr: 'Merci, et c\'est direct ?', en: 'Thanks, and is it direct?' },
        { speaker: 'B', fr: 'Oui, c\'est direct, dix minutes.', en: "Yes, it's direct, ten minutes." },
      ],
      drill: 'Practice asking for a ticket to three destinations you actually go to.',
    },
    {
      id: 3,
      title: 'On board',
      subtitle: 'Getting off at the right stop',
      kind: 'phrases',
      corePhrases: [
        {
          fr: 'Vous descendez à la prochaine ?',
          en: 'Are you getting off at the next stop?',
        },
        { fr: 'Je descends, s\'il vous plaît', en: "I'm getting off, excuse me" },
        {
          fr: 'Le prochain arrêt, s\'il vous plaît ?',
          en: "What's the next stop, please?",
        },
        { fr: 'C\'est bien la direction de… ?', en: 'Is this heading towards…?' },
        { fr: 'Merci, c\'est ici', en: "Thanks, this is my stop" },
      ],
      dialogue: [
        {
          speaker: 'A',
          fr: 'Excusez-moi, vous descendez à la prochaine ?',
          en: 'Excuse me, are you getting off at the next stop?',
        },
        { speaker: 'B', fr: 'Non, allez-y.', en: 'No, go ahead.' },
        {
          speaker: 'A',
          fr: 'Merci ! Le prochain arrêt, s\'il vous plaît ?',
          en: "Thanks! What's the next stop, please?",
        },
        { speaker: 'B', fr: 'Molard, c\'est le prochain.', en: "Molard, it's next." },
        { speaker: 'A', fr: 'Merci, c\'est ici !', en: "Thanks, this is my stop!" },
      ],
      drill: 'Rehearse squeezing past someone and confirming your stop, out loud, 5x.',
    },
    {
      id: 4,
      title: 'Consolidation & role-play',
      subtitle: 'Checkpoint: cross town',
      kind: 'roleplay',
      drill:
        'Combine Sessions 1–3 into one unscripted role-play: from your front door to a tram stop, buy a ticket, ride, and get off at the right stop. This is Week 2\'s checkpoint.',
      roleplaySteps: [
        {
          title: 'Ask a stranger for directions',
          hint: "Excusez-moi, où est l'arrêt de tram ?",
        },
        { title: 'Buy a ticket', hint: 'Un billet pour…, s\'il vous plaît.' },
        { title: 'Confirm the direction', hint: 'C\'est bien la direction de… ?' },
        {
          title: 'Ask to get off / confirm your stop',
          hint: 'Je descends, s\'il vous plaît. Merci, c\'est ici.',
        },
        { title: 'Thank and step off', hint: 'Merci, au revoir !' },
      ],
    },
  ],
  vocab: [
    { fr: 'où', en: 'where' },
    { fr: 'un arrêt', en: 'a stop' },
    { fr: 'un billet', en: 'a ticket' },
    { fr: 'une ligne', en: 'a line (route)' },
    { fr: 'le quai', en: 'the platform' },
    { fr: 'la correspondance', en: 'the transfer/connection' },
    { fr: 'tout droit', en: 'straight ahead' },
    { fr: 'à gauche', en: 'to the left' },
    { fr: 'à droite', en: 'to the right' },
    { fr: 'loin', en: 'far' },
    { fr: 'près', en: 'close/near' },
    { fr: 'un tram', en: 'a tram' },
    { fr: 'un bus', en: 'a bus' },
    { fr: 'la gare', en: 'the train station' },
    { fr: 'descendre', en: 'to get off' },
    { fr: 'monter', en: 'to get on' },
    { fr: 'la direction', en: 'the direction' },
    { fr: 'le prochain', en: 'the next one' },
    { fr: "l'horaire", en: 'the schedule' },
    { fr: 'unireso', en: 'unireso (Geneva\'s unified transport ticket network)' },
  ],
}

export const week3: Week = {
  id: 3,
  title: 'Week 3: Shopping & eating out',
  goal:
    'Buy groceries by weight and price, order a full meal while covering dietary needs, and check opening hours — all in French.',
  sessions: [
    {
      id: 1,
      title: 'At the market',
      subtitle: 'Marché & épicerie basics',
      kind: 'phrases',
      corePhrases: [
        { fr: 'Je cherche…', en: "I'm looking for…" },
        { fr: 'Vous avez… ?', en: 'Do you have… ?' },
        { fr: "C'est combien le kilo ?", en: 'How much per kilo?' },
        { fr: 'Un peu plus', en: 'A bit more' },
        { fr: 'Un peu moins', en: 'A bit less' },
        { fr: 'Ça suffit', en: "That's enough" },
        { fr: "C'est tout, merci", en: "That's all, thanks" },
        { fr: "C'est cher / Ce n'est pas cher", en: "It's expensive / It's not expensive" },
      ],
      grammarSeed:
        'French uses "du", "de la", "des" (some/any) for quantities you can\'t count individually — "du pain" (some bread), "de la confiture" (some jam). Don\'t worry about mastering the rule yet; just recognize it when you hear it at the market.',
      dialogue: [
        {
          speaker: 'A',
          fr: 'Bonjour, je cherche des tomates.',
          en: "Hello, I'm looking for tomatoes.",
        },
        {
          speaker: 'B',
          fr: "Voilà, c'est quatre francs le kilo.",
          en: "Here you go, it's four francs per kilo.",
        },
        {
          speaker: 'A',
          fr: "Un kilo, s'il vous plaît. C'est tout, merci.",
          en: 'One kilo, please. That\'s all, thanks.',
        },
      ],
      drill: 'Ask for three market items with quantities and prices, out loud.',
    },
    {
      id: 2,
      title: 'At the restaurant',
      subtitle: 'Ordering a full meal',
      kind: 'transaction',
      useCases: [
        { phrase: 'Une table pour deux, s\'il vous plaît.', use: 'requesting a table' },
        { phrase: 'Je voudrais réserver une table.', use: 'booking ahead' },
        { phrase: 'Qu\'est-ce que vous recommandez ?', use: 'asking for a recommendation' },
        { phrase: 'Je suis végétarien(ne).', use: 'stating a dietary need' },
        { phrase: 'Y a-t-il du gluten ?', use: 'asking about an allergen' },
        { phrase: "L'addition, s'il vous plaît.", use: 'asking for the bill' },
      ],
      dialogue: [
        {
          speaker: 'A',
          fr: 'Bonsoir, une table pour deux, s\'il vous plaît.',
          en: 'Good evening, a table for two, please.',
        },
        {
          speaker: 'B',
          fr: 'Bien sûr. Voici la carte.',
          en: "Of course. Here's the menu.",
        },
        {
          speaker: 'A',
          fr: 'Merci. Je suis végétarienne — qu\'est-ce que vous recommandez ?',
          en: "Thanks. I'm vegetarian — what do you recommend?",
        },
        {
          speaker: 'B',
          fr: 'La salade de chèvre chaud, c\'est très bon.',
          en: 'The warm goat cheese salad is very good.',
        },
      ],
      drill: 'Order a starter and a main, mention one dietary need, and ask for the bill — out loud, start to finish.',
    },
    {
      id: 3,
      title: 'Days, times & hours',
      subtitle: 'Horaires d\'ouverture',
      kind: 'phrases',
      corePhrases: [
        { fr: "C'est ouvert jusqu'à quelle heure ?", en: 'What time is it open until?' },
        { fr: 'Ouvert / Fermé', en: 'Open / Closed' },
        { fr: 'Aujourd\'hui / Demain / Hier', en: 'Today / Tomorrow / Yesterday' },
        { fr: 'Le matin / L\'après-midi / Le soir', en: 'Morning / Afternoon / Evening' },
        { fr: 'À quelle heure ?', en: 'At what time?' },
        { fr: 'Lundi, mardi, mercredi…', en: 'Monday, Tuesday, Wednesday…' },
      ],
      grammarSeed:
        'Geneva-specific habit: many small shops close Sunday, and some close Monday morning too — always check the posted "horaires" before you make a special trip.',
      dialogue: [
        {
          speaker: 'A',
          fr: "Excusez-moi, c'est ouvert le dimanche ?",
          en: 'Excuse me, is it open on Sundays?',
        },
        {
          speaker: 'B',
          fr: 'Non, fermé le dimanche. Ouvert lundi à samedi, huit heures à dix-huit heures.',
          en: 'No, closed on Sundays. Open Monday to Saturday, 8am to 6pm.',
        },
        { speaker: 'A', fr: "D'accord, merci beaucoup.", en: 'Okay, thank you very much.' },
      ],
      drill: 'Read your own weekly schedule aloud in French: which days you work, and roughly what time.',
    },
    {
      id: 4,
      title: 'Consolidation & role-play',
      subtitle: 'Checkpoint: a day out',
      kind: 'roleplay',
      drill:
        'Combine Sessions 1–3 into one unscripted role-play: check a shop\'s hours, buy groceries by weight, then order a full restaurant meal and pay. This is Week 3\'s checkpoint.',
      roleplaySteps: [
        { title: 'Ask if it\'s open', hint: 'C\'est ouvert jusqu\'à quelle heure ?' },
        { title: 'Ask for a market item by weight', hint: 'C\'est combien le kilo ?' },
        { title: 'Get a restaurant table', hint: 'Une table pour deux, s\'il vous plaît.' },
        { title: 'Mention a dietary need & order', hint: 'Je suis végétarien(ne). Je voudrais…' },
        { title: 'Ask for the bill & thank', hint: 'L\'addition, s\'il vous plaît. Merci, au revoir !' },
      ],
    },
  ],
  vocab: [
    { fr: 'je cherche', en: "I'm looking for" },
    { fr: 'vous avez', en: 'you have (do you have)' },
    { fr: 'un kilo', en: 'a kilo' },
    { fr: 'un peu', en: 'a little' },
    { fr: 'cher', en: 'expensive' },
    { fr: 'une table', en: 'a table' },
    { fr: 'réserver', en: 'to reserve/book' },
    { fr: 'végétarien(ne)', en: 'vegetarian' },
    { fr: "l'addition", en: 'the bill' },
    { fr: "aujourd'hui", en: 'today' },
    { fr: 'demain', en: 'tomorrow' },
    { fr: 'hier', en: 'yesterday' },
    { fr: 'le matin', en: 'the morning' },
    { fr: 'le soir', en: 'the evening' },
    { fr: 'ouvert', en: 'open' },
    { fr: 'fermé', en: 'closed' },
    { fr: 'à quelle heure', en: 'at what time' },
    { fr: 'lundi', en: 'Monday' },
    { fr: 'samedi', en: 'Saturday' },
    { fr: 'dimanche', en: 'Sunday' },
  ],
}

export const week4: Week = {
  id: 4,
  title: 'Week 4: Small talk',
  goal:
    'Hold a two-minute casual conversation — introduce yourself, chat about the weather, and make a simple plan to meet again.',
  sessions: [
    {
      id: 1,
      title: 'Introducing yourself',
      subtitle: "Qui êtes-vous ?",
      kind: 'phrases',
      corePhrases: [
        { fr: "D'où venez-vous ?", en: 'Where are you from?' },
        { fr: 'Je viens de…', en: 'I come from…' },
        { fr: 'Vous habitez où ?', en: 'Where do you live?' },
        { fr: "J'habite à Genève", en: 'I live in Geneva' },
        { fr: 'Vous faites quoi dans la vie ?', en: 'What do you do (for a living)?' },
        { fr: 'Je suis…', en: 'I am (a)…' },
        { fr: 'Depuis combien de temps êtes-vous ici ?', en: 'How long have you been here?' },
        { fr: 'Depuis…', en: 'Since… / For…' },
      ],
      grammarSeed:
        'When stating a profession with "être", French drops the article: "Je suis professeur", not "Je suis un professeur". The article comes back if you add a description: "Je suis un bon professeur."',
      dialogue: [
        { speaker: 'A', fr: "D'où venez-vous ?", en: 'Where are you from?' },
        { speaker: 'B', fr: 'Je viens du Canada, et vous ?', en: "I'm from Canada, and you?" },
        {
          speaker: 'A',
          fr: "Moi, je viens de Genève. Vous êtes ici depuis combien de temps ?",
          en: "I'm from Geneva. How long have you been here?",
        },
        { speaker: 'B', fr: 'Depuis six mois.', en: 'For six months.' },
      ],
      drill: 'Introduce yourself out loud in 30 seconds: your name, where you\'re from, where you live, and what you do.',
    },
    {
      id: 2,
      title: 'Weather & small talk fillers',
      subtitle: 'Quel temps !',
      kind: 'phrases',
      corePhrases: [
        { fr: 'Il fait beau', en: "It's nice out" },
        { fr: 'Il fait froid', en: "It's cold" },
        { fr: 'Il pleut', en: "It's raining" },
        { fr: 'Quel temps !', en: 'What weather!' },
        { fr: 'Ah bon ?', en: 'Oh really?' },
        { fr: 'Vraiment ?', en: 'Really?' },
        { fr: 'Tant mieux', en: 'So much the better / good' },
        { fr: 'Dommage', en: 'Too bad / a shame' },
      ],
      grammarSeed:
        'Weather is the universal small-talk opener — and Geneva\'s weather changes fast, so you\'ll get plenty of practice. These little reaction words ("Ah bon ?", "Vraiment ?", "Dommage") are what actually keep a conversation flowing, more than any grammar rule.',
      dialogue: [
        { speaker: 'A', fr: "Quel temps aujourd'hui, il pleut encore !", en: 'What weather today, it\'s raining again!' },
        { speaker: 'B', fr: 'Ah bon ? Il faisait beau ce matin.', en: 'Oh really? It was nice this morning.' },
        { speaker: 'A', fr: 'Dommage, j\'espérais sortir.', en: 'Too bad, I was hoping to go out.' },
      ],
      drill: 'Comment on today\'s actual weather out loud, then react to an imaginary reply with two different filler words.',
    },
    {
      id: 3,
      title: 'Making plans',
      subtitle: 'On se voit quand ?',
      kind: 'transaction',
      useCases: [
        { phrase: 'On se voit quand ?', use: 'proposing to meet' },
        { phrase: 'Vous êtes libre… ?', use: 'checking availability' },
        { phrase: 'Ça vous dit de… ?', use: 'suggesting an activity' },
        { phrase: 'Avec plaisir', use: 'accepting warmly' },
        { phrase: 'Une autre fois peut-être', use: 'politely declining' },
        { phrase: 'À bientôt', use: 'signing off, expecting to meet again' },
      ],
      dialogue: [
        { speaker: 'A', fr: 'Ça vous dit de prendre un café samedi ?', en: 'Would you like to grab a coffee on Saturday?' },
        { speaker: 'B', fr: 'Avec plaisir ! Vous êtes libre à quelle heure ?', en: 'Gladly! What time are you free?' },
        { speaker: 'A', fr: 'Vers dix heures ?', en: 'Around ten?' },
        { speaker: 'B', fr: "Parfait, à samedi !", en: 'Perfect, see you Saturday!' },
      ],
      drill: 'Propose meeting up three different ways, then practice one polite decline ("Une autre fois peut-être").',
    },
    {
      id: 4,
      title: 'Consolidation & role-play',
      subtitle: 'Checkpoint: meeting someone new',
      kind: 'roleplay',
      drill:
        'Combine Sessions 1–3 into one unscripted role-play: meet someone new, introduce yourself, chat about the weather, and propose a plan to meet again. This is Week 4\'s checkpoint.',
      roleplaySteps: [
        { title: 'Greet & introduce yourself', hint: 'Bonjour, je m\'appelle… Je viens de…' },
        { title: 'Ask about them', hint: 'Vous habitez où ? Vous faites quoi dans la vie ?' },
        { title: 'Comment on the weather', hint: 'Quel temps aujourd\'hui !' },
        { title: 'Propose a plan', hint: 'Ça vous dit de… ? On se voit quand ?' },
        { title: 'Confirm and say goodbye', hint: 'Avec plaisir, à bientôt !' },
      ],
    },
  ],
  vocab: [
    { fr: "d'où", en: 'from where' },
    { fr: 'venir', en: 'to come' },
    { fr: 'habiter', en: 'to live (reside)' },
    { fr: 'la vie', en: 'life' },
    { fr: 'depuis', en: 'since / for (duration)' },
    { fr: 'il fait beau', en: "it's nice out" },
    { fr: 'il pleut', en: "it's raining" },
    { fr: 'froid', en: 'cold' },
    { fr: 'chaud', en: 'hot/warm' },
    { fr: 'vraiment', en: 'really' },
    { fr: 'dommage', en: 'too bad / a shame' },
    { fr: 'tant mieux', en: 'so much the better' },
    { fr: 'libre', en: 'free (available)' },
    { fr: 'avec plaisir', en: 'gladly' },
    { fr: 'à bientôt', en: 'see you soon' },
    { fr: 'une autre fois', en: 'another time' },
    { fr: 'ça vous dit', en: 'does that appeal to you' },
    { fr: 'le temps', en: 'the weather' },
    { fr: 'un rendez-vous', en: 'an appointment / meetup' },
    { fr: 'peut-être', en: 'maybe' },
  ],
}

export const week5: Week = {
  id: 5,
  title: 'Week 5: Health & pharmacy',
  goal:
    'Describe a minor ailment, get advice from a pharmacist, and book a doctor\'s appointment if it\'s serious — entirely in French.',
  sessions: [
    {
      id: 1,
      title: 'Describing symptoms',
      subtitle: "J'ai mal à…",
      kind: 'phrases',
      corePhrases: [
        { fr: "J'ai mal à la tête", en: 'I have a headache' },
        { fr: "J'ai mal au ventre", en: 'I have a stomach ache' },
        { fr: "J'ai mal à la gorge", en: 'I have a sore throat' },
        { fr: "J'ai mal au dos", en: 'I have a backache' },
        { fr: 'Je ne me sens pas bien', en: "I don't feel well" },
        { fr: "J'ai de la fièvre", en: 'I have a fever' },
        { fr: 'Je suis malade', en: "I'm sick" },
        { fr: 'Je tousse', en: "I'm coughing" },
      ],
      grammarSeed:
        '"Avoir mal à" ("to hurt/have pain at") always contracts with the body part\'s article: à + le → au (au ventre), à + la stays à la (à la tête), à + les → aux. It\'s the same au/à la contraction you\'ll start noticing everywhere once you know to listen for it.',
      dialogue: [
        { speaker: 'A', fr: 'Ça va ? Vous avez mauvaise mine.', en: "You okay? You don't look well." },
        { speaker: 'B', fr: 'Non, j\'ai mal à la tête et j\'ai de la fièvre.', en: 'No, I have a headache and a fever.' },
        { speaker: 'A', fr: 'Allez voir un pharmacien.', en: 'Go see a pharmacist.' },
      ],
      drill: 'Describe three different aches out loud, using "j\'ai mal à/au/à la…" for each.',
    },
    {
      id: 2,
      title: 'At the pharmacy',
      subtitle: 'Getting advice & medicine',
      kind: 'transaction',
      useCases: [
        { phrase: 'Avez-vous quelque chose pour… ?', use: 'asking for a recommendation' },
        { phrase: 'Je voudrais un médicament pour…', use: 'asking for medicine directly' },
        { phrase: 'C\'est pour un adulte ou un enfant ?', use: 'the pharmacist confirming who it\'s for' },
        { phrase: 'Combien de fois par jour ?', use: 'asking the dosage frequency' },
        { phrase: 'Est-ce dangereux avec… ?', use: 'checking for interactions' },
      ],
      dialogue: [
        {
          speaker: 'A',
          fr: 'Bonjour, avez-vous quelque chose pour un mal de tête ?',
          en: 'Hello, do you have something for a headache?',
        },
        {
          speaker: 'B',
          fr: 'Oui, voilà. Un comprimé, trois fois par jour.',
          en: 'Yes, here you go. One tablet, three times a day.',
        },
        { speaker: 'A', fr: 'Merci beaucoup.', en: 'Thank you very much.' },
      ],
      drill: 'Ask a pharmacist for medicine for three different ailments (headache, cough, sore throat).',
    },
    {
      id: 3,
      title: "Booking a doctor's visit",
      subtitle: 'Prendre rendez-vous',
      kind: 'transaction',
      useCases: [
        { phrase: 'Je voudrais prendre rendez-vous.', use: 'requesting an appointment' },
        { phrase: 'Vous êtes libre quand ?', use: 'asking about your availability' },
        { phrase: "C'est urgent.", use: 'flagging urgency' },
        { phrase: 'Avez-vous une assurance maladie ?', use: 'the clinic asking about insurance' },
        { phrase: "Le cabinet est ouvert jusqu'à quelle heure ?", use: 'checking clinic hours' },
      ],
      grammarSeed:
        'This recombines Week 3\'s hours/days phrases and Week 4\'s meeting-up phrases into a new context — that\'s deliberate. Real fluency is mostly old vocabulary showing up in new situations, not an endless stream of new words.',
      dialogue: [
        {
          speaker: 'A',
          fr: 'Bonjour, je voudrais prendre rendez-vous, c\'est assez urgent.',
          en: 'Hello, I\'d like to make an appointment, it\'s fairly urgent.',
        },
        { speaker: 'B', fr: 'Vous êtes libre demain matin ?', en: 'Are you free tomorrow morning?' },
        { speaker: 'A', fr: 'Oui, ça marche. Merci.', en: 'Yes, that works. Thanks.' },
      ],
      drill: 'Call and book an appointment out loud: state the reason, agree on a time, thank them.',
    },
    {
      id: 4,
      title: 'Consolidation & role-play',
      subtitle: 'Checkpoint: a sick day',
      kind: 'roleplay',
      drill:
        'Combine Sessions 1–3 into one unscripted role-play: you wake up unwell, describe your symptoms, decide whether to see a pharmacist or book a doctor, and follow through. This is Week 5\'s checkpoint.',
      roleplaySteps: [
        { title: 'Describe how you feel', hint: 'Je ne me sens pas bien. J\'ai mal à…' },
        { title: 'Ask the pharmacist for help', hint: 'Avez-vous quelque chose pour… ?' },
        { title: 'Confirm the dosage', hint: 'Combien de fois par jour ?' },
        { title: 'If it\'s serious, book a doctor', hint: 'Je voudrais prendre rendez-vous, c\'est urgent.' },
        { title: 'Thank and finish', hint: 'Merci beaucoup, au revoir !' },
      ],
    },
  ],
  vocab: [
    { fr: "j'ai mal à", en: 'I have pain at/in' },
    { fr: 'la tête', en: 'the head' },
    { fr: 'le ventre', en: 'the stomach' },
    { fr: 'la gorge', en: 'the throat' },
    { fr: 'le dos', en: 'the back' },
    { fr: 'la fièvre', en: 'fever' },
    { fr: 'malade', en: 'sick' },
    { fr: 'tousser', en: 'to cough' },
    { fr: 'un médicament', en: 'a medicine' },
    { fr: 'une pharmacie', en: 'a pharmacy' },
    { fr: 'un cabinet médical', en: "a doctor's office" },
    { fr: 'un médecin', en: 'a doctor' },
    { fr: 'un rendez-vous', en: 'an appointment' },
    { fr: 'urgent', en: 'urgent' },
    { fr: 'une assurance maladie', en: 'health insurance' },
    { fr: 'quelque chose pour', en: 'something for' },
    { fr: 'une ordonnance', en: 'a prescription' },
    { fr: 'guérir', en: 'to heal / get better' },
    { fr: 'se sentir', en: 'to feel' },
    { fr: 'un comprimé', en: 'a tablet/pill' },
  ],
}

export const week6: Week = {
  id: 6,
  title: 'Week 6: Housing & settling in',
  goal:
    'View an apartment, discuss the basics with a landlord, report a problem, and set up utilities — entirely in French.',
  sessions: [
    {
      id: 1,
      title: 'Apartment viewing',
      subtitle: 'Je cherche un appartement',
      kind: 'phrases',
      corePhrases: [
        { fr: 'Je cherche un appartement', en: "I'm looking for an apartment" },
        { fr: 'un studio', en: 'a studio' },
        { fr: 'Combien de pièces ?', en: 'How many rooms?' },
        { fr: "C'est meublé ou non meublé ?", en: 'Is it furnished or unfurnished?' },
        { fr: 'Le loyer, c\'est combien par mois ?', en: 'How much is the rent per month?' },
        { fr: 'Les charges sont comprises ?', en: 'Are utilities included?' },
        { fr: 'C\'est disponible quand ?', en: 'When is it available?' },
      ],
      grammarSeed:
        '"Combien de" + a noun asks "how many/much of something" — combien de pièces (how many rooms), combien de temps (how much time). It\'s the same "combien" from Week 1\'s "c\'est combien ?", just paired with a noun instead of standing alone.',
      dialogue: [
        {
          speaker: 'A',
          fr: 'Bonjour, je cherche un appartement. Combien de pièces ?',
          en: "Hello, I'm looking at the apartment. How many rooms?",
        },
        {
          speaker: 'B',
          fr: 'Trois pièces, non meublé. Le loyer est de 1800 francs, charges comprises.',
          en: '3 rooms, unfurnished. Rent is 1800 francs, utilities included.',
        },
        { speaker: 'A', fr: "C'est disponible quand ?", en: 'When is it available?' },
        { speaker: 'B', fr: 'Dès le premier du mois.', en: 'From the 1st of the month.' },
      ],
      drill: 'Ask three questions about an apartment out loud: rooms, rent, and availability.',
    },
    {
      id: 2,
      title: 'Talking to the landlord',
      subtitle: 'Signaler un problème',
      kind: 'transaction',
      useCases: [
        { phrase: 'Je voudrais signer le contrat.', use: 'agreeing to a lease' },
        { phrase: 'Il y a un problème avec…', use: 'reporting an issue' },
        { phrase: 'Le chauffage ne marche pas.', use: 'reporting the heating is broken' },
        { phrase: 'Pouvez-vous réparer… ?', use: 'asking for a repair' },
        { phrase: 'Merci de votre compréhension.', use: 'a polite sign-off after a complaint' },
      ],
      grammarSeed:
        '"Il y a" means "there is / there are" — one fixed phrase for both singular and plural. "Il y a un problème" (there\'s a problem), "il y a des charges" (there are fees). You\'ll use it constantly once you notice it.',
      dialogue: [
        {
          speaker: 'A',
          fr: 'Bonjour, il y a un problème : le chauffage ne marche pas.',
          en: "Hello, there's a problem: the heating isn't working.",
        },
        {
          speaker: 'B',
          fr: "D'accord, je viens réparer ça demain.",
          en: "Okay, I'll come fix that tomorrow.",
        },
        { speaker: 'A', fr: 'Merci de votre compréhension.', en: 'Thanks for your understanding.' },
      ],
      drill: 'Report two different problems in an apartment out loud (heating, water, a lock — pick two).',
    },
    {
      id: 3,
      title: 'Utilities & internet',
      subtitle: "S'abonner",
      kind: 'transaction',
      useCases: [
        { phrase: "Je voudrais m'abonner à…", use: 'signing up for a service' },
        { phrase: 'Quand est-ce que ça sera installé ?', use: 'asking about install timing' },
        { phrase: "J'ai besoin d'une connexion internet.", use: 'stating what you need' },
        { phrase: 'un formulaire à remplir', use: 'a form to fill out' },
        { phrase: "le compteur d'électricité", use: 'the electricity meter' },
      ],
      dialogue: [
        {
          speaker: 'A',
          fr: "Bonjour, je voudrais m'abonner à internet pour mon nouvel appartement.",
          en: "Hello, I'd like to sign up for internet for my new apartment.",
        },
        {
          speaker: 'B',
          fr: 'Bien sûr. Quand est-ce que ça sera installé ? On peut faire vendredi.',
          en: 'Of course — when should it be installed? We can do Friday.',
        },
        { speaker: 'A', fr: 'Parfait, merci.', en: 'Perfect, thanks.' },
      ],
      drill: 'Call and set up one utility out loud: state what you need, agree on a date, thank them.',
    },
    {
      id: 4,
      title: 'Consolidation & role-play',
      subtitle: 'Checkpoint: moving in',
      kind: 'roleplay',
      drill:
        'Combine Sessions 1–3 into one unscripted role-play: view an apartment, ask about rent and charges, report an issue once moved in, and set up internet. This is Week 6\'s checkpoint.',
      roleplaySteps: [
        { title: 'Ask about the apartment', hint: 'Combien de pièces ? C\'est meublé ?' },
        { title: 'Ask about rent and charges', hint: 'Le loyer, c\'est combien ? Les charges sont comprises ?' },
        { title: 'Report an issue', hint: 'Il y a un problème avec… Pouvez-vous réparer… ?' },
        { title: 'Set up internet', hint: 'Je voudrais m\'abonner à internet.' },
        { title: 'Thank and confirm', hint: 'Merci beaucoup, à bientôt !' },
      ],
    },
  ],
  vocab: [
    { fr: 'un appartement', en: 'an apartment' },
    { fr: 'un studio', en: 'a studio apartment' },
    { fr: 'une pièce', en: 'a room' },
    { fr: 'le loyer', en: 'the rent' },
    { fr: 'les charges', en: 'utilities/fees' },
    { fr: 'meublé', en: 'furnished' },
    { fr: 'disponible', en: 'available' },
    { fr: 'signer', en: 'to sign' },
    { fr: 'un contrat', en: 'a contract' },
    { fr: 'réparer', en: 'to fix/repair' },
    { fr: 'le chauffage', en: 'the heating' },
    { fr: 'un problème', en: 'a problem' },
    { fr: "s'abonner", en: 'to subscribe / sign up' },
    { fr: 'une connexion', en: 'a connection' },
    { fr: 'un formulaire', en: 'a form' },
    { fr: 'le compteur', en: 'the meter' },
    { fr: "l'électricité", en: 'electricity' },
    { fr: 'un locataire', en: 'a tenant' },
    { fr: 'un propriétaire', en: 'a landlord/owner' },
    { fr: 'un concierge', en: 'a building caretaker' },
  ],
}

export const week7: Week = {
  id: 7,
  title: 'Week 7: Banking & post office',
  goal:
    'Open a bank account, send a package at the post office, and fill out a basic form — entirely in French.',
  sessions: [
    {
      id: 1,
      title: 'At the bank',
      subtitle: 'Ouvrir un compte',
      kind: 'phrases',
      corePhrases: [
        { fr: 'Je voudrais ouvrir un compte.', en: 'I would like to open an account.' },
        { fr: 'un compte bancaire', en: 'a bank account' },
        { fr: 'un compte d\'épargne', en: 'a savings account' },
        { fr: 'une carte de crédit', en: 'a credit card' },
        { fr: 'Quels documents faut-il ?', en: 'What documents are needed?' },
        { fr: 'Il y a des frais mensuels ?', en: 'Are there monthly fees?' },
      ],
      grammarSeed:
        '"Il faut" + a verb means "one must / it\'s necessary to" — a fixed impersonal phrase like "il y a", never conjugated to match a person. "Il faut remplir un formulaire" (you need to fill out a form), "il faut deux documents" (two documents are needed).',
      dialogue: [
        {
          speaker: 'A',
          fr: 'Bonjour, je voudrais ouvrir un compte bancaire.',
          en: "Hello, I'd like to open a bank account.",
        },
        {
          speaker: 'B',
          fr: 'Bien sûr. Il faut une pièce d\'identité et un justificatif de domicile.',
          en: 'Of course. You\'ll need an ID and proof of address.',
        },
        { speaker: 'A', fr: 'Il y a des frais mensuels ?', en: 'Are there monthly fees?' },
        { speaker: 'B', fr: 'Non, ce compte est gratuit.', en: "No, this account is free." },
      ],
      drill: 'Ask three questions about opening a bank account out loud.',
    },
    {
      id: 2,
      title: 'At the post office',
      subtitle: 'La Poste',
      kind: 'transaction',
      useCases: [
        { phrase: 'Je voudrais envoyer un colis.', use: 'sending a package' },
        { phrase: 'une lettre', use: 'a letter' },
        { phrase: "Combien coûte l'envoi ?", use: 'asking the shipping cost' },
        { phrase: 'Il faut combien de jours ?', use: 'asking how many days it takes' },
        { phrase: 'Un timbre, s\'il vous plaît.', use: 'buying a stamp' },
      ],
      dialogue: [
        {
          speaker: 'A',
          fr: 'Bonjour, je voudrais envoyer ce colis en France.',
          en: 'Hello, I\'d like to send this package to France.',
        },
        {
          speaker: 'B',
          fr: "Ça fait douze francs. Il faut deux jours.",
          en: "That's twelve francs. It takes two days.",
        },
        { speaker: 'A', fr: "Parfait, merci.", en: 'Perfect, thanks.' },
      ],
      drill: 'Practice sending a package and asking about delivery time, start to finish.',
    },
    {
      id: 3,
      title: 'Filling out forms',
      subtitle: 'Remplir un formulaire',
      kind: 'phrases',
      corePhrases: [
        { fr: 'Remplissez ce formulaire.', en: 'Fill out this form.' },
        { fr: 'Signez ici.', en: 'Sign here.' },
        { fr: 'Votre nom et prénom', en: 'Your last name and first name' },
        { fr: 'Votre date de naissance', en: 'Your date of birth' },
        { fr: 'Votre adresse', en: 'Your address' },
        { fr: 'Cochez la case.', en: 'Check the box.' },
      ],
      grammarSeed:
        '"Remplissez", "signez", "cochez" are imperatives — commands built from the "vous" form of the verb, minus "vous" itself. It\'s how instructions and official forms talk to you, and how you\'d politely instruct someone back.',
      dialogue: [
        {
          speaker: 'A',
          fr: 'Remplissez ce formulaire, s\'il vous plaît : nom, prénom, et date de naissance.',
          en: 'Please fill out this form: last name, first name, and date of birth.',
        },
        { speaker: 'B', fr: "D'accord, et je signe où ?", en: 'Okay, and where do I sign?' },
        { speaker: 'A', fr: 'Signez ici, et cochez cette case.', en: 'Sign here, and check this box.' },
      ],
      drill: 'Read a mock form aloud field by field: nom, prénom, date de naissance, adresse.',
    },
    {
      id: 4,
      title: 'Consolidation & role-play',
      subtitle: 'Checkpoint: errands day',
      kind: 'roleplay',
      drill:
        'Combine Sessions 1–3 into one unscripted role-play: open a bank account, send a package at the post office, and fill out a form along the way. This is Week 7\'s checkpoint.',
      roleplaySteps: [
        { title: 'Ask to open an account', hint: 'Je voudrais ouvrir un compte.' },
        { title: 'Ask about fees & documents', hint: 'Quels documents faut-il ? Il y a des frais ?' },
        { title: 'Send a package', hint: 'Je voudrais envoyer un colis. Combien coûte l\'envoi ?' },
        { title: 'Fill out the form', hint: 'Remplissez ce formulaire. Signez ici.' },
        { title: 'Thank and leave', hint: 'Merci beaucoup, au revoir !' },
      ],
    },
  ],
  vocab: [
    { fr: 'un compte', en: 'an account' },
    { fr: 'la banque', en: 'the bank' },
    { fr: 'une carte de crédit', en: 'a credit card' },
    { fr: 'des frais', en: 'fees' },
    { fr: 'un document', en: 'a document' },
    { fr: 'un colis', en: 'a package' },
    { fr: 'une lettre', en: 'a letter' },
    { fr: 'un timbre', en: 'a stamp' },
    { fr: 'envoyer', en: 'to send' },
    { fr: 'la poste', en: 'the post office' },
    { fr: 'remplir', en: 'to fill out' },
    { fr: 'un formulaire', en: 'a form' },
    { fr: 'signer', en: 'to sign' },
    { fr: 'cocher', en: 'to check (a box)' },
    { fr: 'une case', en: 'a box (on a form)' },
    { fr: 'une adresse', en: 'an address' },
    { fr: 'la date de naissance', en: 'date of birth' },
    { fr: 'il faut', en: 'one must / it takes' },
    { fr: 'gratuit', en: 'free (no cost)' },
    { fr: "une pièce d'identité", en: 'an ID document' },
  ],
}

export const weeks: Week[] = [week1, week2, week3, week4, week5, week6, week7]
