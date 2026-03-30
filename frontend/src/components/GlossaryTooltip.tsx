import { useState } from 'react';

const DEFINITIONS: Record<string, string> = {
  SEQ: 'A numbered pairing of flights spanning one or more duty days.',
  TPAY: 'Total credited pay time for the sequence.',
  TAFB: 'Total elapsed time from report at base to release at base.',
  SYNTH: 'Additional credited time beyond actual block time.',
  OPS: 'Number of times a sequence operates in the bid period.',
  POSN: 'Crew position range for the sequence.',
  LANG: 'Language qualification required for the sequence.',
  DH: 'Deadhead — a positioning flight as a passenger.',
  EQ: 'Equipment — the aircraft type for a leg.',
  RPT: 'Report time — check-in time before first leg.',
  RLS: 'Release time — off-duty time after last leg.',
  DP: 'Duty Period — a working day within a sequence.',
  'PAX SVC': 'Passenger service code for cabin service level.',
};

export function GlossaryTerm({ term, children }: { term: string; children?: React.ReactNode }) {
  const [show, setShow] = useState(false);
  const def = DEFINITIONS[term];
  if (!def) return <>{children || term}</>;

  const tooltipId = `glossary-${term.replace(/\s+/g, '-').toLowerCase()}`;

  return (
    <span
      className="relative inline-block border-b border-dotted border-gray-400 cursor-help"
      tabIndex={0}
      role="term"
      aria-describedby={show ? tooltipId : undefined}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)}
      onBlur={() => setShow(false)}
      onKeyDown={(e) => { if (e.key === 'Escape') setShow(false); }}
    >
      {children || term}
      {show && (
        <span id={tooltipId} role="tooltip" className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 rounded-md bg-gray-900 px-3 py-2 text-xs text-white shadow-lg z-50">
          <span className="font-medium">{term}</span>: {def}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </span>
      )}
    </span>
  );
}
