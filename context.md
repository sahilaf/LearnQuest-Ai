# LearnQuest AI

## AI-Powered Personalized Learning Platform with a Real-Time Avatar Tutor

---

# Title Page

## Project Title

**LearnQuest AI: AI-Powered Personalized Learning Platform with a Real-Time Avatar Tutor**

## Project Type

Software Development Project

## Team Members

| Member | Responsibility |
| --- | --- |
| Member 1 (Team Lead) | AI Avatar Tutor, Adaptive Learning Engine, AI Integration |
| Member 2 | Learning Management Module |
| Member 3 | Course & User Management Module |
| Member 4 | Gamification & Analytics Module |

---

# 1. Project Overview

LearnQuest AI is a web-based learning platform built on a single idea:

> **A tutor that models the student's mind, not just their score.**

Conventional platforms record *whether* an answer was wrong. LearnQuest infers **why** — it identifies the underlying false belief, states it in plain English, and stores it as a tracked misconception. It then does something no mainstream platform does: it **inverts the tutoring relationship**. A photoreal AI tutor is seeded with the student's own misconception, and the student must explain them out of it. The tutor's subsequent score on the same question becomes the student's grade.

This is grounded in the *protégé effect*, a well-documented finding in education research: people learn more preparing to teach, and more still when teaching, than when studying for themselves.

Around that core the platform provides an AI-generated learning roadmap, adaptive lessons, AI-generated quizzes, practice problems, and progress tracking, with gamification (XP, badges, streaks, challenges) to sustain motivation.

The application is designed to be completely web-based and built using free and open-source technologies wherever possible.

---

# 2. Problem Definition

Current online learning platforms have several limitations:

- Every learner receives the same learning path.
- Students often lose motivation due to repetitive learning.
- AI chatbots answer questions but do not guide long-term learning.
- Progress tracking is usually limited to quiz scores.
- Learning platforms rarely provide interactive tutoring.

Students require a learning environment that can adapt to their pace, remember previous learning sessions, and make studying more engaging.

---

# 3. Motivation

Learning is different for every individual.

Some students learn through examples while others learn through practice. Some require more revision while others progress quickly.

The motivation behind LearnQuest AI is to create an intelligent learning assistant capable of:

- Providing personalized guidance
- Keeping students engaged
- Tracking learning progress
- Encouraging consistency through gamification
- Making online learning feel interactive and conversational

---

# 4. Objectives

The project aims to:

- Build an AI-powered personalized learning platform
- Develop a real-time avatar tutor
- Generate quizzes using AI
- Recommend learning content based on user progress
- Track learning performance
- Motivate students through gamification
- Create an intuitive and modern learning experience

---

# 5. Target Users

- University students
- School students
- Self-learners
- Online learners
- Competitive exam candidates

---

# 6. Functional Features

## 6.1 Authentication

- User Registration
- User Login
- Password Reset
- Secure Authentication
- User Profile

---

## 6.2 Dashboard

The dashboard displays:

- Current Level
- XP
- Learning Streak
- Completed Lessons
- Daily Goals
- Weak Topics
- Recommended Lessons
- Recent Activities

---

## 6.3 AI Avatar Tutor

The AI tutor is the central feature of the platform.

The tutor appears as a real-time animated avatar capable of speaking naturally while interacting with the student.

### Features

- Real-time conversation
- Natural responses
- Lip synchronization
- Facial animation
- Conversation history
- Context awareness
- Personalized interactions
- Topic explanations
- Study guidance
- **Teach-Back mode** - the student teaches the tutor (see 6.10)

The avatar uses our own pipeline powered by **SyncTalk**, a trained audio-driven
talking-head model, rather than a third-party avatar framework. The service
streams rendered frames over a WebSocket alongside synchronised audio.

There is one avatar: SyncTalk. The placeholder SVG avatar ("Tier A") was
removed on 2026-09-22 — two avatars meant two lipsync paths and two voices that
could both fire at once, and the cartoon silently replaced the real tutor
exactly when you most wanted to know something was wrong.

It needs two things, and `GET /api/avatar/status` reports both:

- the **SyncTalk service** reachable at `AVATAR_SERVICE_URL`, and
- a **speech provider**, because the service renders frames only in response to
  audio. Gemini TTS returns 24 kHz PCM, which is the rate SyncTalk works in.

With either missing the UI shows an "avatar offline" panel naming the reason.
The tutor still answers in text, and Teach-Back runs normally.

---

## 6.4 Personalized Learning

The platform keeps track of:

- Completed lessons
- Quiz performance
- Weak topics
- Strong topics
- Learning history

Based on this information, students receive:

- Recommended lessons
- Suggested revision
- Personalized quizzes
- Daily learning plans

---

## 6.5 AI Quiz Generator

The platform automatically generates quizzes.

Question Types:

- Multiple Choice
- True/False
- Fill in the Blank
- Short Answer

Difficulty adapts based on student performance.

---

## 6.6 Course Module

Students can

- Browse courses
- Enroll in courses
- Read lessons
- Watch videos
- Complete quizzes
- Track completion

---

## 6.7 Progress Tracking

Students can monitor

- Overall Progress
- Course Completion
- Quiz Performance
- Learning Time
- Topic Mastery
- Weekly Activity

---

## 6.8 Gamification

The platform rewards learning through:

- XP Points
- Coins
- Badges
- Daily Streaks
- Achievement Cards
- Daily Challenges
- Level System

---

## 6.9 Admin Panel

Administrator can

- Manage Courses
- Manage Users
- Upload Learning Materials
- View Analytics
- Monitor Platform Usage

---

## 6.10 Misconception Engine and Teach-Back *(novel contribution)*

This is the platform's research claim and its main point of difference.

### 6.10.1 Error Autopsy

When an answer is wrong, the system does not stop at "incorrect". An LLM is asked
to infer the **false belief** that produced the answer and to state it in plain
English, for example:

> *You believe "FULL JOIN" returns only rows present in both tables. "Full"
> actually means keep every row from both sides, matched or not.*

The misconception is stored against the topic (`topic_mastery.misconception`),
tracked over time, and decays through **active → fading → cleared** as the
student answers correctly. If the model cannot identify a belief with confidence,
nothing is stored - inventing a misconception is worse than recording none.

### 6.10.2 Teach-Back ("Teach Nova")

The tutoring relationship is then inverted. The avatar is seeded with the
student's *own* misconception and presents it as its own confusion. It asks naive
questions and pushes back when an explanation is vague. The student must talk it
out of the mistake.

The avatar then re-attempts the original question, and **its score becomes the
student's grade**. The student is assessed on how well they taught, not on how
well they guessed.

### 6.10.3 Why this is novel

Existing platforms (Duolingo, HackerRank, Khan Academy) model a single mastery
score per topic and deliver explanations *to* the learner. Modelling the *causes*
of error, and using a photoreal agent as a deliberately flawed protégé, is not
offered by any mainstream system. The pairing is what makes it work: arguing with
a face that looks confused is a materially different experience from typing into
a chat box.

---

## 6.11 AI Learning Roadmap

Rather than a fixed curriculum, each student states a goal ("become backend-ready
in eight weeks") and receives a generated roadmap.

- The planner is **grounded in the real catalogue**: it may only select and order
  lessons that actually exist. Any invented topic is discarded before the plan is
  stored, so a hallucinated skill can never reach a student.
- The result is a **directed acyclic graph**, not a list - independent tracks can
  run in parallel and nodes unlock as their prerequisites complete.
- The roadmap **re-plans** as mastery changes and as misconceptions are detected,
  inserting remediation where the student is weak.
- If the model is unavailable, a deterministic fallback orders the catalogue by
  curriculum sequence, and the UI states plainly that the AI planner did not run.

The interface is a branching skill map in the style of roadmap.sh.

---

## 6.12 Practice Problems

Structured in the style of HackerRank: **Tracks → Skills → Problems**, each
problem carrying a difficulty label, solve rate, and completion status, with
skill verification once enough problems are solved.

---

# 7. Non-Functional Requirements

- Responsive Design
- Secure Authentication
- Fast API Response
- Scalable Architecture
- Mobile Friendly
- Modern User Interface
- Easy Navigation
- Modular Codebase

---

# 8. Tools and Technologies

## Frontend

- React.js
- Tailwind CSS
- React Router
- Framer Motion

---

## Backend

- FastAPI
- Python
- SQLAlchemy

---

## Database

- PostgreSQL

---

## AI

- OpenAI API (or another compatible LLM API)
- LangChain (optional for workflow management)

---

## Avatar

- SyncTalk
- Browser Speech API (optional)
- WebRTC (for real-time streaming if required)

---

## Authentication

- Supabase Auth

---

## Deployment

Frontend

- Vercel

Backend

- Render

Database

- Supabase PostgreSQL (Free Tier)

---

## Version Control

- Git
- GitHub

---

# 9. Strengths

- Personalized learning experience
- Interactive AI tutor
- Real-time animated avatar
- Adaptive quiz generation
- Progress tracking
- Gamification
- Free technology stack
- Modern UI
- Modular architecture

---

# 10. Weaknesses

- AI responses depend on API quality.
- Free hosting has resource limitations.
- Avatar performance depends on client hardware.
- Large AI conversations may increase latency.
- Requires an internet connection.

---

# 11. Gap Analysis

| Existing Platform | Limitation | LearnQuest AI Solution |
| --- | --- | --- |
| ChatGPT | General-purpose assistant without structured learning | Personalized learning with progress tracking |
| Google Classroom | Course management only | Interactive AI tutoring with personalized recommendations |
| Moodle | Static learning management | AI-generated quizzes and adaptive learning |
| Coursera | Fixed course progression | Personalized lesson recommendations |
| Duolingo | Limited to predefined content | AI-powered learning across multiple subjects with an avatar tutor |

---

# 12. System Modules

The project is divided into complete feature modules rather than frontend/backend separation so each team member owns an end-to-end feature.

---

## Module 1 — AI Avatar Tutor & Intelligent Learning (Team Lead)

This is the core module of the project.

Responsibilities:

- AI Tutor integration
- SyncTalk avatar implementation
- Real-time avatar animation
- AI conversation system
- Conversation memory
- Personalized learning recommendations
- AI quiz generation
- Prompt engineering
- AI service integration
- Avatar response pipeline
- Integration with all other modules

Deliverables:

- Fully functional AI tutor
- Animated avatar
- Personalized recommendations
- AI-generated quizzes

---

## Module 2 — Learning Management Module

Responsibilities:

- Course management
- Lesson pages
- Chapter navigation
- Study materials
- Quiz interface
- Assignment pages
- Student dashboard
- Learning history
- Responsive UI for learning workflow

Deliverables:

- Complete learning experience from enrollment to lesson completion.

---

## Module 3 — User & Administration Module

Responsibilities:

- Authentication
- User profile
- Student management
- Admin dashboard
- Course CRUD
- User settings
- Database management
- REST APIs
- Security
- Deployment support

Deliverables:

- Complete user management system.

---

## Module 4 — Gamification & Analytics Module

Responsibilities:

- XP system
- Badge system
- Daily challenges
- Streak tracking
- Leaderboard
- Progress analytics
- Statistics dashboard
- Achievement system
- Notifications
- Final testing and bug reporting

Deliverables:

- Complete gamification ecosystem with analytics.

---

# 13. Project Timeline

## Week 1

- Project setup
- Database design
- UI design
- Authentication
- Avatar prototype
- Basic course module

---

## Week 2

- AI tutor integration
- Course pages
- User management
- Quiz module
- Dashboard development
- XP system

---

## Week 3

- Avatar synchronization
- Personalized recommendations
- Progress tracking
- Daily challenges
- Admin panel
- Analytics

---

## Week 4

- Feature integration
- Testing
- Bug fixing
- Performance optimization
- Deployment
- Documentation
- Final presentation

---

# 14. Expected Deliverables

- Fully functional web application
- AI-powered avatar tutor
- Personalized learning dashboard
- Course management system
- AI-generated quizzes
- Gamification system
- Progress analytics
- Admin dashboard
- Source code repository
- User documentation
- Deployment link

---

# 15. Future Enhancements

- Voice conversation with the avatar
- Multi-language support
- Mobile application
- Group study rooms
- Calendar integration
- Offline learning mode
- Parent dashboard
- Teacher dashboard
- AI-generated study notes
- AI-powered flashcards

---

# Estimated Development Scope

- Duration: **1 Month**
- Team Size: **4 Members**
- Development Methodology: **Agile (Weekly Sprints)**
- Platform: **Web Application**
- Estimated Pages: **15–20**
- Estimated APIs: **20+**
- Database Tables: **12–15**
- Primary Goal: Deliver a complete, polished AI-powered personalized learning platform using free-tier services and open-source technologies.