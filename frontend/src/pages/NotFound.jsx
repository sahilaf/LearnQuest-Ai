import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-4xl font-bold">404</h1>
      <p className="text-slate-500">That page does not exist.</p>
      <Link to="/dashboard" className="text-primary-600 hover:underline">
        Back to dashboard
      </Link>
    </div>
  );
}
