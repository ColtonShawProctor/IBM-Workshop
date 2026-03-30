import { useState } from 'react';

interface GlossaryEntry {
  term: string;
  abbreviation: string;
  definition: string;
}

const GLOSSARY: GlossaryEntry[] = [
  { term: 'Sequence', abbreviation: 'SEQ', definition: 'A numbered pairing of flights that starts and ends at the base city, spanning one or more duty days. The fundamental unit flight attendants bid on.' },
  { term: 'Leg', abbreviation: '', definition: 'A single flight within a sequence, from one station to another.' },
  { term: 'Duty Period', abbreviation: 'DP', definition: 'A working day within a sequence, which may contain one or more legs.' },
  { term: 'Block Time', abbreviation: '', definition: 'The time from pushback to gate arrival for a flight leg; the primary unit of flight time.' },
  { term: 'Time Away From Base', abbreviation: 'TAFB', definition: 'Total elapsed time from report at base to release at base for the entire sequence.' },
  { term: 'Total Pay', abbreviation: 'TPAY', definition: 'The total credited pay time for the sequence, which may include synthetic credit.' },
  { term: 'Synthetic', abbreviation: 'SYNTH', definition: 'Additional credited time beyond actual block time, per contractual rules.' },
  { term: 'Report Time', abbreviation: 'RPT', definition: 'The time a flight attendant must check in before the first leg of a duty period, shown as local/home-base time.' },
  { term: 'Release Time', abbreviation: 'RLS', definition: 'The time a flight attendant is released after the last leg of a duty period, shown as local/home-base time.' },
  { term: 'Deadhead', abbreviation: 'DH', definition: 'A positioning flight where the flight attendant rides as a passenger (indicated by a "D" suffix on the flight number). Deadhead legs do not count as working block time.' },
  { term: 'Operations', abbreviation: 'OPS', definition: 'The number of times a sequence operates within the bid period (e.g., "25 OPS" means it runs 25 times that month).' },
  { term: 'Position', abbreviation: 'POSN', definition: 'The crew position range for the sequence (e.g., "1 THRU 9" for widebody, "1 THRU 4" for narrowbody).' },
  { term: 'Language Qualification', abbreviation: 'LANG', definition: 'Language qualification required for the sequence (e.g., "LANG JP 3" means 3 positions require Japanese).' },
  { term: 'Equipment', abbreviation: 'EQ', definition: 'The aircraft type for a given leg (e.g., 777, 787, narrowbody variants).' },
  { term: 'Station', abbreviation: 'STA', definition: 'An airport code (e.g., ORD, LHR, NRT, LAS).' },
  { term: 'Passenger Service', abbreviation: 'PAX SVC', definition: 'Passenger service code indicating the cabin service level for a leg (e.g., QLF, QDB, QLS).' },
  { term: 'Red-eye', abbreviation: '', definition: 'A flight that departs late at night and arrives early the next morning.' },
  { term: 'Turn / Day Trip', abbreviation: '', definition: 'A single-day sequence that departs and returns to base the same day with no overnight layover.' },
  { term: 'Layover', abbreviation: '', definition: 'An overnight rest stop at a city away from base between duty periods, including hotel and ground transportation details.' },
  { term: 'Ground Time', abbreviation: '', definition: 'Time between legs on the same duty day (connections); marked with "X" when it is a connection.' },
  { term: 'Rest', abbreviation: '', definition: 'Minimum off-duty time between duty periods at a layover city.' },
  { term: 'Base City', abbreviation: '', definition: 'The flight attendant\'s home airport where all sequences originate and terminate (e.g., ORD).' },
  { term: 'Bid Period', abbreviation: '', definition: 'The month for which the bid sheet is effective (e.g., January 1\u201330).' },
  { term: 'Attainability', abbreviation: '', definition: 'An estimate of how likely you are to be awarded a sequence given your seniority. High = likely, Medium = possible, Low = unlikely.' },
  { term: 'Date Conflict Group', abbreviation: '', definition: 'A set of sequences whose operating dates overlap. You can only be awarded one sequence from each conflict group.' },
  { term: 'Preference Score', abbreviation: '', definition: 'A 0\u2013100% score showing how well a sequence matches your weighted preferences (TPAY target, layover cities, report times, etc.).' },
  { term: 'Coverage Rate', abbreviation: '', definition: 'The percentage of bid period dates covered by at least one ranked sequence. Low coverage increases the risk of reserve assignment.' },
  { term: 'Reserve', abbreviation: '', definition: 'On-call duty where flight attendants are assigned trips as needed with little advance notice. Avoided by submitting a well-covered bid.' },
];

export default function GlossaryPage() {
  const [search, setSearch] = useState('');

  const filtered = search.trim()
    ? GLOSSARY.filter((g) =>
        g.term.toLowerCase().includes(search.toLowerCase()) ||
        g.abbreviation.toLowerCase().includes(search.toLowerCase()) ||
        g.definition.toLowerCase().includes(search.toLowerCase())
      )
    : GLOSSARY;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Glossary</h1>
        <p className="text-sm text-gray-500 mt-1">Airline scheduling terminology</p>
      </div>

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search terms..."
        className="w-full max-w-md rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
      />

      <div className="space-y-1">
        {filtered.map((entry) => (
          <div key={entry.term} className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="flex items-baseline gap-2">
              <span className="font-medium text-gray-900">{entry.term}</span>
              {entry.abbreviation && (
                <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs font-mono text-gray-600">{entry.abbreviation}</span>
              )}
            </div>
            <p className="text-sm text-gray-600 mt-1">{entry.definition}</p>
          </div>
        ))}
        {filtered.length === 0 && (
          <p className="text-sm text-gray-400">No matching terms.</p>
        )}
      </div>
    </div>
  );
}
