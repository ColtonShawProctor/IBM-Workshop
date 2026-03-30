import { useEffect, useState } from 'react';
import { isOnline, onStatusChange, getQueueLength } from '../lib/offline';

export default function OnlineStatus() {
  const [online, setOnline] = useState(isOnline());
  const [queueLen, setQueueLen] = useState(getQueueLength());

  useEffect(() => {
    const unsub = onStatusChange((status) => {
      setOnline(status);
      setQueueLen(getQueueLength());
    });
    return unsub;
  }, []);

  if (online && queueLen === 0) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={online ? (queueLen > 0 ? `Online, ${queueLen} pending changes` : 'Online') : 'Offline, changes will sync when reconnected'}
      className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium ${
        online ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
      }`}
    >
      <span aria-hidden="true" className={`w-2 h-2 rounded-full ${online ? 'bg-green-500' : 'bg-red-500'}`} />
      {online ? 'Online' : 'Offline'}
      {queueLen > 0 && (
        <span className="text-gray-500">({queueLen} pending)</span>
      )}
    </div>
  );
}
