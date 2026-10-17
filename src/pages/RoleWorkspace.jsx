import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import { useLang } from "@/lib/i18n/LanguageContext";
import {
  archiveService,
  assignApplicationToStaff,
  completeApplicationTask,
  createApplicationTask,
  createService,
  createStaffAccount,
  deleteService,
  listApplications,
  listApplicationTasks,
  listOwnerUsers,
  listServices,
  publishService,
  updateAdminUserRole,
  updateAdminUserStatus,
  updateService,
} from "@/api/backendClient";
import StatusBadge from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { FileText, Plus, Users, ClipboardList, AlertCircle } from "lucide-react";

const ROLES = ["customer", "staff", "owner", "admin"];

export default function RoleWorkspace() {
  const { user } = useAuth();
  const { loc, lang } = useLang();
  const [applications, setApplications] = useState([]);
  const [staff, setStaff] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [users, setUsers] = useState([]);
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [staffForm, setStaffForm] = useState({ fullName: "", mobile: "", password: "" });
  const [taskForm, setTaskForm] = useState({ applicationId: "", staffId: "", title: "", dueDate: "", priority: "normal" });
  const [serviceForm, setServiceForm] = useState({ code: "", nameMr: "", nameEn: "", nameHi: "", category: "Certificates", documents: "" });

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      if (user.role === "owner") {
        const [applicationPage, staffPage, taskPage] = await Promise.all([
          listApplications(), listOwnerUsers("staff"), listApplicationTasks(),
        ]);
        setApplications(applicationPage.items || []);
        setStaff(staffPage.items || []);
        setTasks(taskPage.items || []);
      } else if (user.role === "staff") {
        const applicationPage = await listApplications();
        setApplications(applicationPage.items || []);
      } else if (user.role === "admin") {
        const [applicationPage, userPage, servicePage] = await Promise.all([
          listApplications(), listOwnerUsers(), listServices(lang, true),
        ]);
        setApplications(applicationPage.items || []);
        setUsers(userPage.items || []);
        setServices(servicePage.items || []);
      }
    } catch (loadError) {
      setError(loadError.message || "Unable to load workspace");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [user.role, lang]);

  const runAction = async (action, successMessage) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(successMessage);
      await load();
      return true;
    } catch (actionError) {
      setError(actionError.message || "Unable to complete this action");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const createStaff = (event) => {
    event.preventDefault();
    runAction(
      () => createStaffAccount(staffForm.fullName.trim(), staffForm.mobile, staffForm.password),
      "Staff account created.",
    ).then((success) => { if (success) setStaffForm({ fullName: "", mobile: "", password: "" }); });
  };

  const createTask = (event) => {
    event.preventDefault();
    const dueDate = taskForm.dueDate ? new Date(`${taskForm.dueDate}T23:59:00`).toISOString() : null;
    runAction(
      () => createApplicationTask({
        title: taskForm.title,
        application_id: taskForm.applicationId || null,
        assigned_staff_id: taskForm.staffId,
        priority: taskForm.priority,
        due_date: dueDate,
      }),
      "Checklist task assigned.",
    ).then((success) => { if (success) setTaskForm({ applicationId: "", staffId: "", title: "", dueDate: "", priority: "normal" }); });
  };

  const createNewService = async (event) => {
    event.preventDefault();
    const documentRequirements = serviceForm.documents.split(/\r?\n/).map((label, index) => label.trim())
      .filter(Boolean).map((label, index) => ({
        id: `${serviceForm.code.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${String(index + 1).padStart(2, "0")}`,
        label: { mr: label },
        required: true,
      }));
    if (!documentRequirements.length) {
      setError("Add at least one required document before publishing a service.");
      return;
    }
    const success = await runAction(async () => {
      const result = await createService({
        service_code: serviceForm.code.trim().toUpperCase(),
        name: { mr: serviceForm.nameMr.trim(), en: serviceForm.nameEn.trim(), hi: serviceForm.nameHi.trim() },
        description: {
          mr: "प्राधिकरणाकडून अतिरिक्त कागदपत्रे मागितली जाऊ शकतात.",
          en: "The responsible authority may request additional documents.",
          hi: "संबंधित प्राधिकरण अतिरिक्त दस्तावेज़ मांग सकता है।",
        },
        category: serviceForm.category.trim(),
        document_requirements: documentRequirements,
      });
      await updateService(result.id, { checklist_review_required: false });
      await publishService(result.id);
    }, "Service created and published.");
    if (success) setServiceForm({ code: "", nameMr: "", nameEn: "", nameHi: "", category: "Certificates", documents: "" });
  };

  const title = user.role === "owner" ? "Owner workspace" : user.role === "staff" ? "Staff workspace" : "Admin workspace";

  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-primary">{user.role}</p>
        <h1 className="font-heading font-bold text-2xl md:text-3xl text-foreground">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Signed in as {user.full_name}</p>
      </div>

      {error && <div role="alert" className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive flex gap-2"><AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />{error}</div>}
      {notice && <p role="status" className="mb-4 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">{notice}</p>}
      {loading ? <div className="py-16 text-center text-muted-foreground">Loading workspace…</div> : (
        <>
          {(user.role === "owner" || user.role === "staff" || user.role === "admin") && (
            <section className="mb-10">
              <h2 className="font-heading font-semibold text-xl mb-4 flex items-center gap-2"><FileText className="w-5 h-5" />{user.role === "staff" ? "Assigned applications (read-only)" : user.role === "admin" ? "All customer applications" : "Customer applications"}</h2>
              {applications.length === 0 ? (
                <div className="rounded-xl border border-dashed border-border p-10 text-center text-muted-foreground">No applications are assigned or submitted yet.</div>
              ) : (
                <div className="space-y-3">
                  {applications.map((application) => (
                    <div key={application.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4">
                      <Link to={`/applications/${application.id}`} className="min-w-0 flex-1 hover:text-primary">
                        <p className="font-medium truncate">{loc(application, "service_name") || application.service?.name?.mr || application.application_number}</p>
                        <p className="text-xs text-muted-foreground">{application.application_number} · {application.priority || "normal"} priority{application.internal_due_date ? ` · due ${new Date(application.internal_due_date).toLocaleDateString()}` : ""}</p>
                      </Link>
                      <StatusBadge status={application.status} />
                      {user.role === "owner" && (
                        <select
                          aria-label={`Assign ${application.application_number} to staff`}
                          className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                          value={application.assigned_staff_id || ""}
                          disabled={busy || !staff.length}
                          onChange={(event) => {
                            if (event.target.value) runAction(() => assignApplicationToStaff(application.id, event.target.value), "Application assigned.");
                          }}
                        >
                          <option value="">Unassigned</option>
                          {staff.map((member) => <option key={member._id} value={member._id}>{member.full_name}</option>)}
                        </select>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {user.role === "staff" && (
            <div className="rounded-xl border border-border bg-muted/20 p-5 text-sm text-muted-foreground">
              Staff access is limited to reading assigned applications, copying application details, and downloading customer-provided files. Status, review, and document changes are restricted to owners and administrators.
            </div>
          )}

          {user.role === "owner" && (
            <>
              <section className="mb-10 rounded-xl border border-border bg-card p-5">
                <h2 className="font-heading font-semibold text-xl mb-1 flex items-center gap-2"><ClipboardList className="w-5 h-5" />Priority and due-date checklist</h2>
                <p className="text-sm text-muted-foreground mb-4">Assign follow-up tasks to staff and set a due date and priority.</p>
                <form onSubmit={createTask} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  <input required minLength={2} placeholder="Task / next action" className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={taskForm.title} onChange={(event) => setTaskForm({ ...taskForm, title: event.target.value })} />
                  <select required className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={taskForm.staffId} onChange={(event) => setTaskForm({ ...taskForm, staffId: event.target.value })}>
                    <option value="">Assign staff…</option>
                    {staff.map((member) => <option key={member._id} value={member._id}>{member.full_name}</option>)}
                  </select>
                  <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={taskForm.applicationId} onChange={(event) => setTaskForm({ ...taskForm, applicationId: event.target.value })}>
                    <option value="">General task</option>
                    {applications.map((application) => <option key={application.id} value={application.id}>{application.application_number}</option>)}
                  </select>
                  <input aria-label="Task due date" type="date" className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={taskForm.dueDate} onChange={(event) => setTaskForm({ ...taskForm, dueDate: event.target.value })} />
                  <div className="flex gap-2">
                    <select aria-label="Task priority" className="h-10 min-w-0 flex-1 rounded-md border border-input bg-background px-2 text-sm" value={taskForm.priority} onChange={(event) => setTaskForm({ ...taskForm, priority: event.target.value })}>
                      {["low", "normal", "high", "urgent"].map((priority) => <option key={priority}>{priority}</option>)}
                    </select>
                    <Button type="submit" disabled={busy || !staff.length}><Plus className="w-4 h-4 mr-1" />Assign</Button>
                  </div>
                </form>
                {!staff.length && <p className="mt-3 text-sm text-muted-foreground">Create a staff account below before assigning tasks.</p>}
              </section>

              <section className="mb-10">
                <h2 className="font-heading font-semibold text-xl mb-4">Open checklist tasks</h2>
                {tasks.length === 0 ? <p className="text-sm text-muted-foreground">No tasks created yet.</p> : (
                  <div className="space-y-2">
                    {tasks.map((task) => (
                      <div key={task._id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card p-3">
                        <div><p className="font-medium">{task.title}</p><p className="text-xs text-muted-foreground">{task.priority} · {task.due_date ? `Due ${new Date(task.due_date).toLocaleString()}` : "No due date"} · {task.status}</p></div>
                        {task.status !== "completed" && task.status !== "cancelled" && <Button size="sm" variant="outline" disabled={busy} onClick={() => runAction(() => completeApplicationTask(task._id), "Task marked complete.")}>Mark complete</Button>}
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="rounded-xl border border-border bg-card p-5">
                <h2 className="font-heading font-semibold text-xl mb-1 flex items-center gap-2"><Users className="w-5 h-5" />Staff accounts</h2>
                <p className="text-sm text-muted-foreground mb-4">Staff can only view assigned applications and download or copy their data.</p>
                <form onSubmit={createStaff} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 mb-5">
                  <input required minLength={2} placeholder="Full name" className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={staffForm.fullName} onChange={(event) => setStaffForm({ ...staffForm, fullName: event.target.value })} />
                  <input required inputMode="numeric" placeholder="10-digit mobile" className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={staffForm.mobile} onChange={(event) => setStaffForm({ ...staffForm, mobile: event.target.value })} />
                  <input required minLength={10} type="password" autoComplete="new-password" placeholder="Temporary password (10+ chars)" className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={staffForm.password} onChange={(event) => setStaffForm({ ...staffForm, password: event.target.value })} />
                  <Button type="submit" disabled={busy}>Create staff account</Button>
                </form>
                <div className="divide-y divide-border">
                  {staff.map((member) => <p key={member._id} className="py-2 text-sm">{member.full_name} <span className="text-muted-foreground">· {member.mobile_number} · {member.account_status}</span></p>)}
                </div>
              </section>
            </>
          )}

          {user.role === "admin" && (
            <>
              <section className="mb-10 rounded-xl border border-border bg-card p-5">
                <h2 className="font-heading font-semibold text-xl mb-1 flex items-center gap-2"><Users className="w-5 h-5" />Account and role management</h2>
                <p className="text-sm text-muted-foreground mb-4">Choose a role for each account. Role or status changes revoke existing sessions.</p>
                <div className="space-y-2">
                  {users.map((account) => (
                    <div key={account._id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-3">
                      <div><p className="font-medium">{account.full_name}</p><p className="text-xs text-muted-foreground">{account.mobile_number} · {account.account_status}</p></div>
                      <div className="flex gap-2">
                        <select aria-label={`Role for ${account.full_name}`} disabled={account._id === (user._id || user.id) || busy} className="h-9 rounded-md border border-input bg-background px-2 text-sm" value={account.role} onChange={(event) => runAction(() => updateAdminUserRole(account._id, event.target.value), "Account role updated.")}>
                          {ROLES.map((role) => <option key={role}>{role}</option>)}
                        </select>
                        <Button size="sm" variant="outline" disabled={account._id === (user._id || user.id) || busy} onClick={() => runAction(() => updateAdminUserStatus(account._id, account.account_status === "active" ? "suspended" : "active"), "Account status updated.")}>
                          {account.account_status === "active" ? "Suspend" : "Activate"}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
              <section className="mb-10 rounded-xl border border-border bg-card p-5">
                <h2 className="font-heading font-semibold text-xl mb-1">Add a service</h2>
                <p className="text-sm text-muted-foreground mb-4">Add verified document requirements; newly created services are published once the checklist is saved.</p>
                <form onSubmit={createNewService} className="space-y-3">
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <input required pattern="[A-Za-z0-9_-]+" placeholder="Service code (e.g. NEW_SERVICE)" className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={serviceForm.code} onChange={(event) => setServiceForm({ ...serviceForm, code: event.target.value })} />
                    <input required placeholder="Service name (Marathi)" className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={serviceForm.nameMr} onChange={(event) => setServiceForm({ ...serviceForm, nameMr: event.target.value })} />
                    <input required placeholder="Service name (English)" className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={serviceForm.nameEn} onChange={(event) => setServiceForm({ ...serviceForm, nameEn: event.target.value })} />
                    <input required placeholder="Service name (Hindi)" className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={serviceForm.nameHi} onChange={(event) => setServiceForm({ ...serviceForm, nameHi: event.target.value })} />
                  </div>
                  <input required placeholder="Category" className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm" value={serviceForm.category} onChange={(event) => setServiceForm({ ...serviceForm, category: event.target.value })} />
                  <textarea required rows={5} placeholder="Required documents, one per line" className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" value={serviceForm.documents} onChange={(event) => setServiceForm({ ...serviceForm, documents: event.target.value })} />
                  <Button type="submit" disabled={busy}>Create and publish service</Button>
                </form>
              </section>
              <section className="rounded-xl border border-border bg-card p-5">
                <h2 className="font-heading font-semibold text-xl mb-4">Service catalog ({services.length})</h2>
                <div className="space-y-2">
                  {services.map((service) => (
                    <div key={service.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-3">
                      <div><p className="font-medium">{loc(service, "name")}</p><p className="text-xs text-muted-foreground">{service.service_code} · {service.is_published ? "Published" : "Unpublished"} · {service.checklist?.length || 0} checklist items</p></div>
                      <div className="flex gap-2">
                        {service.is_published
                          ? <Button size="sm" variant="outline" disabled={busy} onClick={() => runAction(() => archiveService(service.id), "Service archived.")}>Archive</Button>
                          : <Button size="sm" variant="outline" disabled={busy || !service.checklist?.length} onClick={() => runAction(() => publishService(service.id), "Service published.")}>Publish</Button>}
                        <Button size="sm" variant="destructive" disabled={busy} onClick={() => {
                          if (window.confirm("Delete this service permanently? Services with applications must be archived instead.")) {
                            runAction(() => deleteService(service.id), "Service deleted.");
                          }
                        }}>Delete</Button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}
