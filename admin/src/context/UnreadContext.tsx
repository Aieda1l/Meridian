import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { getUnreadCount } from '../api/client';

interface UnreadContextType {
  unreadCount: number;
  setUnreadCount: (count: number) => void;
  refresh: () => Promise<void>;
}

const UnreadContext = createContext<UnreadContextType>({
  unreadCount: 0,
  setUnreadCount: () => {},
  refresh: async () => {},
});

export function UnreadProvider({ children }: { children: ReactNode }) {
  const [unreadCount, setUnreadCount] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const data = await getUnreadCount();
      setUnreadCount(data.count);
    } catch {
      // Silently ignore
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <UnreadContext.Provider value={{ unreadCount, setUnreadCount, refresh }}>
      {children}
    </UnreadContext.Provider>
  );
}

export const useUnread = () => useContext(UnreadContext);
