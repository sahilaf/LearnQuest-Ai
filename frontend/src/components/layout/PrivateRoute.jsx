/** Blocks unauthenticated access. OWNER: Member 3. */
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import Spinner from '../ui/Spinner';

export default function PrivateRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
