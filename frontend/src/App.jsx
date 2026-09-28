import { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';

import AppLayout from './components/layout/AppLayout';
import PrivateRoute from './components/layout/PrivateRoute';
import AdminRoute from './components/layout/AdminRoute';

// The shell and the front door are needed immediately, so they stay in the
// main chunk. Everything else is split per route.
import Landing from './pages/Landing/Landing';
import NotFound from './pages/NotFound';

// Unified Hubs
const LearnHub = lazy(() => import('./pages/Learn/LearnHub'));
const ProgressHub = lazy(() => import('./pages/Progress/ProgressHub'));

// --- Member 3: auth, profile, admin ---
const Login = lazy(() => import('./pages/Auth/Login'));
const Register = lazy(() => import('./pages/Auth/Register'));
const ForgotPassword = lazy(() => import('./pages/Auth/ForgotPassword'));
const Profile = lazy(() => import('./pages/Profile/Profile'));
const AdminOverview = lazy(() => import('./pages/Admin/AdminOverview'));
const AdminUsers = lazy(() => import('./pages/Admin/AdminUsers'));
const AdminCourses = lazy(() => import('./pages/Admin/AdminCourses'));
const UploadNotes = lazy(() => import('./pages/Upload/UploadNotes'));

// --- Member 2: learning ---
const Dashboard = lazy(() => import('./pages/Dashboard/Dashboard'));
const CourseDetail = lazy(() => import('./pages/Courses/CourseDetail'));
const LessonViewer = lazy(() => import('./pages/Lesson/LessonViewer'));
const QuizPlayer = lazy(() => import('./pages/Quiz/QuizPlayer'));
const QuizResult = lazy(() => import('./pages/Quiz/QuizResult'));
const ProblemViewer = lazy(() => import('./pages/Practice/ProblemViewer'));
const ReviewScreen = lazy(() => import('./pages/Review/ReviewScreen'));

// --- Member 1: tutor & avatar ---
const TutorPage = lazy(() => import('./pages/Tutor/TutorPage'));

/**
 * Shown while a route chunk downloads. Deliberately quiet: a full-page skeleton
 * that flashes for 80ms is more distracting than a small spinner.
 */
function RouteFallback() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <span className="h-6 w-6 animate-spin rounded-full border-2 border-line-strong border-t-primary-400" />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        {/* public landing page - the app's front door.
            Landing itself redirects signed-in visitors to /dashboard. */}
        <Route path="/" element={<Landing />} />

        {/* public - Member 3 */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />

        {/* authenticated shell */}
        <Route
          element={
            <PrivateRoute>
              <AppLayout />
            </PrivateRoute>
          }
        >
          {/* Main 5 Primary Navigation Views */}
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/home" element={<Navigate to="/dashboard" replace />} />
          <Route path="/learn" element={<LearnHub />} />
          <Route path="/review" element={<ReviewScreen />} />
          <Route path="/tutor" element={<TutorPage />} />
          <Route path="/tutor/:conversationId" element={<TutorPage />} />
          <Route path="/progress" element={<ProgressHub />} />

          {/* Deep links & Learning details */}
          <Route path="/courses/:slug" element={<CourseDetail />} />
          <Route path="/lessons/:lessonId" element={<LessonViewer />} />
          <Route path="/quiz/:quizId" element={<QuizPlayer />} />
          <Route path="/quiz/attempts/:attemptId" element={<QuizResult />} />
          <Route path="/practice/:problemId" element={<ProblemViewer />} />

          {/* Legacy redirects into unified Hubs */}
          <Route path="/courses" element={<Navigate to="/learn?tab=browse" replace />} />
          <Route path="/roadmap" element={<Navigate to="/learn?tab=roadmap" replace />} />
          <Route path="/practice" element={<Navigate to="/learn?tab=sql-challenges" replace />} />
          <Route path="/stats" element={<Navigate to="/progress?tab=stats" replace />} />
          <Route path="/achievements" element={<Navigate to="/progress?tab=achievements" replace />} />
          <Route path="/leaderboard" element={<Navigate to="/progress?tab=leaderboard" replace />} />
          <Route path="/history" element={<Navigate to="/progress?tab=history" replace />} />

          {/* Member 3 */}
          <Route path="/profile" element={<Profile />} />
          <Route path="/upload" element={<UploadNotes />} />

          {/* Member 3 - admin only */}
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <AdminOverview />
              </AdminRoute>
            }
          />
          <Route
            path="/admin/users"
            element={
              <AdminRoute>
                <AdminUsers />
              </AdminRoute>
            }
          />
          <Route
            path="/admin/courses"
            element={
              <AdminRoute>
                <AdminCourses />
              </AdminRoute>
            }
          />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
