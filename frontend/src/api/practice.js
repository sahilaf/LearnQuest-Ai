/**
 * Practice problems & skill verification. OWNER: Member 2 (UI) / Member 1 (runner).
 * All requests go through the shared client.
 *
 * Problems are SQL, graded by actually running them: the backend executes the
 * student's query in an isolated in-memory database and compares the result
 * with a reference solution, across visible and hidden test cases.
 *
 * There is deliberately NO client-side fallback. There used to be one, and when
 * the backend was missing it "graded" by passing any code longer than 15
 * characters, echoing the expected output back as the actual output, and
 * inventing a randomised runtime so it looked real. A student could not tell it
 * apart from a working judge. An error is honest; that was not.
 */
import client from './client';

/** {items: [{id, slug, title, skill_id, skill_name, topic_tag, difficulty,
 *            status, acceptance_rate, total_submissions, statement_md}], total} */
export const listProblems = (params = {}) => client.get('/api/practice/problems', { params });

/** Full problem. Never includes the reference solution or any case's seed data;
 *  hidden test cases come back without `expected_output`. Accepts id or slug. */
export const getProblem = (problemRef) => client.get(`/api/practice/problems/${problemRef}`);

/**
 * Run every test case against the query and record the attempt.
 *
 * {attempt_id, all_passed, passed_test_cases, total_test_cases, skill_verified,
 *  test_case_results: [{test_case_id, title, is_hidden, status, expected_output,
 *                       actual_output, error, execution_ms}]}
 *
 * `status` is 'passed' | 'failed' | 'error'. Hidden cases report pass or fail
 * only - their data is shown as "(Hidden)".
 */
export const submitProblem = (problemRef, { code }) =>
  client.post(`/api/practice/problems/${problemRef}/submit`, { code });

/** {items: [{id, name, required_to_verify, passed_count, verified}]} */
export const getSkillStatus = () => client.get('/api/practice/skills');
