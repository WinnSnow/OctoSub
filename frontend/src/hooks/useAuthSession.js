import { useEffect, useState } from 'react';

import { getCurrentUser, logout } from '../api/auth';
import { setUnauthorizedHandler } from '../api/client';

export function useAuthSession() {
  const [authLoading, setAuthLoading] = useState(true);
  const [user, setUser] = useState(null);

  useEffect(() => {
    return setUnauthorizedHandler(() => setUser(null));
  }, []);

  useEffect(() => {
    getCurrentUser()
      .then(response => setUser(response.data.user))
      .catch(() => setUser(null))
      .finally(() => setAuthLoading(false));
  }, []);

  const logoutUser = async () => {
    try {
      await logout();
    } finally {
      setUser(null);
    }
  };

  return { authLoading, user, setUser, logoutUser };
}
