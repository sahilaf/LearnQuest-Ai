/**
 * Application router.
 *
 * SHARED FILE - change only by agreement (plan.md 2.4).
 *
 * All four members' route groups are registered here already so nobody has to
 * touch this file again. Build inside your own pages/ folder instead.
 */
import { Routes, Route, Navigate } from 'react-router-dom';

import AppLayout from './components/layout/AppLayout';
import PrivateRoute from './components/layout/PrivateRoute';
import AdminRoute from './components/layout/AdminRoute';
import NotFound from './pages/NotFound';

// --- Member 3: auth, profile, admin ---
import Login from './pages/Auth/Login';
import Register from './pages/Auth/Register';
import ForgotPassword from './pages/Auth/ForgotPassword';
import Profile from './pages/Profile/Profile';
import AdminOverview from './pages/Admin/AdminOverview';
import AdminUsers from './pages/Admin/AdminUsers';
import AdminCourses from './pages/Admin/AdminCourses';

// --- Member 2: learning ---
import Dashboard from './pages/Dashboard/Dashboard';
import CourseCatalog from './pages/Courses/CourseCatalog';
import CourseDetail from './pages/Courses/CourseDetail';
import LessonViewer from './pages/Lesson/LessonViewer';
import QuizPlayer from './pages/Quiz/QuizPlayer';
import QuizResult from './pages/Quiz/QuizResult';
import History from './pages/History/History';

// --- Member 1: tutor & avatar ---
import TutorPage from './pages/Tutor/TutorPage';

// --- Member 4: gamification & analytics ---
import Achievements from './pages/Achievements/Achievements';
import Leaderboard from './pages/Leaderboard/Leaderboard';
import Stats from './pages/Stats/Stats';

export default function App() {
  return (
    <Routes>
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
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        {/* Member 2 */}
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/courses" element={<CourseCatalog />} />
        <Route path="/courses/:slug" element={<CourseDetail />} />
        <Route path="/lessons/:lessonId" element={<LessonViewer />} />
        <Route path="/quiz/:quizId" element={<QuizPlayer />} />
        <Route path="/quiz/attempts/:attemptId" element={<QuizResult />} />
        <Route path="/history" element={<History />} />

        {/* Member 1 */}
        <Route path="/tutor" element={<TutorPage />} />
        <Route path="/tutor/:conversationId" element={<TutorPage />} />

        {/* Member 4 */}
        <Route path="/achievements" element={<Achievements />} />
        <Route path="/leaderboard" element={<Leaderboard />} />
        <Route path="/stats" element={<Stats />} />

        {/* Member 3 */}
        <Route path="/profile" element={<Profile />} />

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
  );
}
