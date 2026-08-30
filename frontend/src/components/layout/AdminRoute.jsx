/** Blocks non-admin access. OWNER: Member 3. */
import { Navigate } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';

export default function AdminRoute({ children }) {
  const { isAdmin } = useAuth();
  if (!isAdmin) return <Navigate to="/dashboard" replace />;
  return children;
}
