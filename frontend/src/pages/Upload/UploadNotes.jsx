/**
 * Upload Notes -> Course. OWNER: Member 3.
 * See plan.md §6.13, §7.2 #5, §8.6, and CHECKLIST.md Slot 11.
 *
 * Lets a student drag & drop a PDF, Markdown, or text file to extract text,
 * split into structured lessons, tag with vocabulary, and create a private course.
 */
import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  BookOpen,
  Clock,
  Tag,
  Edit2,
  Check,
  RotateCcw,
} from 'lucide-react';

import { uploadNotes, updateCourse, updateLesson } from '../../api/courses';
import PageHeader from '../../components/layout/PageHeader';
import { Badge, Button, Card, Input } from '../../components/ui';

export default function UploadNotes() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [customTitle, setCustomTitle] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  // Result state
  const [generatedResult, setGeneratedResult] = useState(null);
  const [editingCourseTitle, setEditingCourseTitle] = useState(false);
  const [courseTitleInput, setCourseTitleInput] = useState('');
  const [editingLessonId, setEditingLessonId] = useState(null);
  const [lessonTitleInput, setLessonTitleInput] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleSelectedFile(e.target.files[0]);
    }
  };

  const handleSelectedFile = (selected) => {
    setError(null);
    const validExtensions = ['.pdf', '.md', '.markdown', '.txt'];
    const nameLower = selected.name.toLowerCase();
    const isValid = validExtensions.some((ext) => nameLower.endsWith(ext));

    if (!isValid) {
      setError('Please select a valid PDF (.pdf), Markdown (.md), or text (.txt) file.');
      return;
    }

    if (selected.size > 10 * 1024 * 1024) {
      setError('File size exceeds the 10 MB limit.');
      return;
    }

    setFile(selected);
    const baseName = selected.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ');
    setCustomTitle(baseName.charAt(0).toUpperCase() + baseName.slice(1));
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await uploadNotes(formData, customTitle.trim() || undefined);
      const data = res?.data || res;
      setGeneratedResult(data);
      setCourseTitleInput(data.course.title);
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to process file and generate course.';
      setError(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleSaveCourseTitle = async () => {
    if (!courseTitleInput.trim() || !generatedResult) return;
    setSavingEdit(true);
    try {
      await updateCourse(generatedResult.course.id, { title: courseTitleInput.trim() });
      setGeneratedResult((prev) => ({
        ...prev,
        course: { ...prev.course, title: courseTitleInput.trim() },
      }));
      setEditingCourseTitle(false);
    } catch (err) {
      setError('Failed to update course title.');
    } finally {
      setSavingEdit(false);
    }
  };

  const handleSaveLessonTitle = async (lessonId) => {
    if (!lessonTitleInput.trim() || !generatedResult) return;
    setSavingEdit(true);
    try {
      await updateLesson(generatedResult.course.id, lessonId, {
        title: lessonTitleInput.trim(),
      });
      setGeneratedResult((prev) => ({
        ...prev,
        lessons: prev.lessons.map((l) =>
          l.id === lessonId ? { ...l, title: lessonTitleInput.trim() } : l
        ),
      }));
      setEditingLessonId(null);
    } catch (err) {
      setError('Failed to update lesson title.');
    } finally {
      setSavingEdit(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setCustomTitle('');
    setGeneratedResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Upload your notes"
        subtitle="Turn lecture slides, PDFs, or Markdown notes into a private course with lessons, practice, and spaced review."
      />

      {error && (
        <div className="flex items-start gap-3 rounded border border-hard/30 bg-hard-bg p-4 text-sm text-hard-fg">
          <AlertCircle className="h-5 w-5 shrink-0 text-hard" />
          <div className="flex-1">
            <p className="font-medium">Upload Notice</p>
            <p className="mt-1 text-xs">{error}</p>
          </div>
        </div>
      )}

      {!generatedResult ? (
        <Card className="p-6">
          <form onSubmit={handleUpload} className="space-y-6">
            {/* Drag & Drop Zone */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`flex cursor-pointer flex-col items-center justify-center rounded border-2 border-dashed p-8 text-center transition-colors ${
                isDragging
                  ? 'border-primary-500 bg-primary-500/5'
                  : file
                  ? 'border-easy/60 bg-easy-bg/20'
                  : 'border-line hover:border-line-strong hover:bg-raised/40'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.md,.markdown,.txt"
                className="hidden"
                onChange={handleFileChange}
              />

              {file ? (
                <div className="flex flex-col items-center space-y-2">
                  <div className="flex h-12 w-12 items-center justify-center rounded bg-easy-bg text-easy-fg">
                    <FileText className="h-6 w-6" />
                  </div>
                  <div className="font-semibold text-ink">{file.name}</div>
                  <div className="text-2xs text-muted">
                    {(file.size / 1024).toFixed(1)} KB &bull; Click or drag to replace
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center space-y-2">
                  <div className="flex h-12 w-12 items-center justify-center rounded bg-canvas text-muted">
                    <UploadCloud className="h-6 w-6" />
                  </div>
                  <div>
                    <span className="font-semibold text-ink">Choose a document</span>
                    <span className="text-muted"> or drag & drop it here</span>
                  </div>
                  <p className="text-2xs text-muted">
                    Supports PDF, Markdown (.md), or plain text (.txt) up to 10 MB
                  </p>
                </div>
              )}
            </div>

            {/* Course Title Option */}
            {file && (
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-muted">
                  Course Title (Optional)
                </label>
                <Input
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  placeholder="e.g. Database Systems Lecture Notes"
                  disabled={uploading}
                />
              </div>
            )}

            {/* Action Bar */}
            <div className="flex items-center justify-between border-t border-line/60 pt-4">
              <span className="text-2xs text-muted">
                Private course &bull; Visible only to your account
              </span>
              <Button
                type="submit"
                variant="primary"
                size="md"
                disabled={!file || uploading}
              >
                {uploading ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                    Generating course...
                  </>
                ) : (
                  <>
                    <UploadCloud className="h-4 w-4" />
                    Create Course
                  </>
                )}
              </Button>
            </div>
          </form>
        </Card>
      ) : (
        /* Generated Course Result & Editing */
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-2 flex-1">
                <div className="flex items-center gap-2">
                  <Badge tone="easy">Private Course</Badge>
                  <Badge tone="neutral">Uploaded Notes</Badge>
                  <Badge tone="info">{generatedResult.course.difficulty}</Badge>
                </div>

                {editingCourseTitle ? (
                  <div className="flex items-center gap-2 pt-1">
                    <Input
                      value={courseTitleInput}
                      onChange={(e) => setCourseTitleInput(e.target.value)}
                      className="max-w-md"
                      disabled={savingEdit}
                    />
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleSaveCourseTitle}
                      disabled={savingEdit}
                    >
                      <Check className="h-4 w-4" />
                      Save
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditingCourseTitle(false)}
                      disabled={savingEdit}
                    >
                      Cancel
                    </Button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2.5">
                    <h2 className="text-xl font-semibold text-ink">
                      {generatedResult.course.title}
                    </h2>
                    <button
                      type="button"
                      onClick={() => setEditingCourseTitle(true)}
                      className="text-muted hover:text-ink"
                      title="Edit title"
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                  </div>
                )}

                <p className="text-xs text-muted">
                  {generatedResult.course.description}
                </p>

                {/* Topics covered */}
                <div className="flex flex-wrap items-center gap-1.5 pt-2">
                  <span className="text-2xs text-muted flex items-center gap-1 mr-1">
                    <Tag className="h-3 w-3" /> Topics:
                  </span>
                  {generatedResult.topics.map((tag) => (
                    <span
                      key={tag}
                      className="rounded bg-canvas px-2 py-0.5 font-mono text-2xs text-muted"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Button variant="secondary" size="sm" onClick={handleReset}>
                  <RotateCcw className="h-3.5 w-3.5" />
                  Upload another
                </Button>
                <Button
                  variant="primary"
                  size="md"
                  onClick={() => navigate(`/courses/${generatedResult.course.slug}`)}
                >
                  Start Course
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </Card>

          {/* Lessons List */}
          <Card className="p-0">
            <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-primary-600" />
                <h3 className="text-sm font-semibold text-ink">
                  Generated Lessons ({generatedResult.lessons.length})
                </h3>
              </div>
              <span className="text-xs text-muted flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                ~{generatedResult.course.estimated_hours}h estimated study time
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="table-dense w-full">
                <thead>
                  <tr>
                    <th className="w-12">#</th>
                    <th>Lesson Title</th>
                    <th>Topics</th>
                    <th>Est. Time</th>
                    <th className="text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {generatedResult.lessons.map((lesson, idx) => (
                    <tr key={lesson.id}>
                      <td className="font-mono text-muted">{idx + 1}</td>
                      <td>
                        {editingLessonId === lesson.id ? (
                          <div className="flex items-center gap-2">
                            <Input
                              value={lessonTitleInput}
                              onChange={(e) => setLessonTitleInput(e.target.value)}
                              className="text-xs"
                              disabled={savingEdit}
                            />
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={() => handleSaveLessonTitle(lesson.id)}
                              disabled={savingEdit}
                            >
                              <Check className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setEditingLessonId(null)}
                              disabled={savingEdit}
                            >
                              Cancel
                            </Button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2 font-medium text-ink">
                            <span>{lesson.title}</span>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingLessonId(lesson.id);
                                setLessonTitleInput(lesson.title);
                              }}
                              className="text-muted hover:text-ink opacity-60 hover:opacity-100"
                              title="Edit lesson title"
                            >
                              <Edit2 className="h-3 w-3" />
                            </button>
                          </div>
                        )}
                      </td>
                      <td>
                        <div className="flex flex-wrap gap-1">
                          {lesson.topic_tags.map((t) => (
                            <span
                              key={t}
                              className="rounded bg-canvas px-1.5 py-0.5 font-mono text-2xs text-muted"
                            >
                              {t}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="text-muted text-xs">
                        {lesson.estimated_minutes} min
                      </td>
                      <td className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/lessons/${lesson.id}`)}
                        >
                          View lesson
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
