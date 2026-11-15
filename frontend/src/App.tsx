import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  FileText,
  History,
  Home,
  Link2,
  LoaderCircle,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  UserRoundCheck,
  Users
} from "lucide-react";
import {
  createContext,
  FormEvent,
  ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState
} from "react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams
} from "react-router-dom";
import {
  api,
  ApiError,
  Draft,
  EvidenceState,
  Material,
  Member,
  patch,
  post,
  Project,
  RequestDetail,
  Sections,
  setApiMember,
  Task,
  TaskEvent
} from "./api";

const sectionMeta: Array<[keyof Sections, string, string]> = [
  ["completed", "已完成事项", "已经完成且可被材料支持的工作"],
  ["decisions", "关键决策及理由", "选择了什么，以及为什么"],
  ["verification", "验证情况", "检查输出；没有证据时明确未验证"],
  ["open_issues", "遗留问题", "阻塞、风险和未知事项"],
  ["next_steps", "下一步建议", "建议接手者继续做什么"]
];

const progressLabels: Record<string, string> = {
  not_started: "未开始",
  in_progress: "进行中",
  blocked: "受阻",
  completed: "完成"
};
const reviewLabels: Record<string, string> = {
  draft: "待审核",
  confirmed: "已确认",
  needs_review: "需重新审核"
};
const requestLabels: Record<string, string> = {
  none: "未发起",
  pending: "待接收",
  needs_info: "待补充",
  rejected: "已拒绝",
  accepted: "已接收",
  expired: "已过期"
};
const evidenceLabels: Record<EvidenceState, string> = {
  current: "证据有效",
  stale: "来源已有新版本",
  missing: "固定来源缺失",
  mismatch: "证据哈希不匹配",
  unauthorized: "来源不属于当前任务"
};

function EvidenceNotice({ state }: { state: EvidenceState }) {
  const current = state === "current";
  return (
    <div className={"evidence-state " + state} role={current ? undefined : "alert"}>
      {current ? <ShieldCheck size={18} /> : <AlertTriangle size={18} />}
      <span>
        <strong>{evidenceLabels[state]}</strong>
        <small>{current ? "引用版本、正文与哈希均已核对。" : "请返回材料重新审核、确认并发起交接。"}</small>
      </span>
    </div>
  );
}

type SessionValue = {
  members: Member[];
  member: Member;
  changeMember: (id: string) => void;
  resetDemo: () => Promise<void>;
};
const SessionContext = createContext<SessionValue | null>(null);
const useSession = () => {
  const value = useContext(SessionContext);
  if (!value) throw new Error("Session unavailable");
  return value;
};

function useLoad<T>(loader: () => Promise<T>, dependencies: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const reload = () => {
    setLoading(true);
    setError("");
    loader()
      .then(setData)
      .catch((reason: ApiError) => setError(reason.message))
      .finally(() => setLoading(false));
  };
  useEffect(reload, dependencies);
  return { data, error, loading, reload };
}

function fmt(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function ErrorNotice({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="notice error" role="alert">
      <AlertTriangle size={18} aria-hidden />
      <span>{message}</span>
    </div>
  );
}

function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={22} aria-hidden />
      正在读取最新状态…
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty">
      <FileText size={24} aria-hidden />
      <p>{children}</p>
    </div>
  );
}

function AppShell({ children }: { children: ReactNode }) {
  const { members, member, changeMember, resetDemo } = useSession();
  const location = useLocation();
  const [resetting, setResetting] = useState(false);
  const reset = async () => {
    setResetting(true);
    await resetDemo();
    setResetting(false);
    window.location.assign("/");
  };
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand" aria-label="交接工作台首页">
          <span className="brand-mark"><ShieldCheck size={20} /></span>
          <span><strong>交接工作台</strong><small>人工确认 · 主动接收</small></span>
        </Link>
        <div className="topbar-actions">
          <span className="demo-pill">本地 Demo</span>
          <label className="identity">
            <span className="sr-only">切换演示身份</span>
            <select value={member.id} onChange={(event) => changeMember(event.target.value)}>
              {members.map((item) => (
                <option key={item.id} value={item.id}>{item.display_name} · {item.role_label}</option>
              ))}
            </select>
          </label>
          <button className="icon-button" onClick={reset} disabled={resetting} title="重置演示数据">
            <RefreshCw className={resetting ? "spin" : ""} size={18} />
          </button>
        </div>
      </header>
      <nav className="crumbbar" aria-label="当前位置">
        <Link to="/"><Home size={15} />项目</Link>
        {location.pathname !== "/" && <span className="crumb-current">工作区</span>}
      </nav>
      <main>{children}</main>
      <footer>AI 仅整理文字。确认内容、发起交接与主动接收始终由团队成员完成。</footer>
    </div>
  );
}

export function App() {
  const [members, setMembers] = useState<Member[]>([]);
  const [memberId, setMemberId] = useState(localStorage.getItem("handoff-member") ?? "");
  const [bootError, setBootError] = useState("");

  useEffect(() => {
    api<{ items: Member[] }>("/demo/members")
      .then((response) => {
        setMembers(response.items);
        const selected = response.items.some((item) => item.id === memberId)
          ? memberId
          : response.items[0]?.id ?? "";
        setMemberId(selected);
        setApiMember(selected);
      })
      .catch((error: ApiError) => setBootError(error.message));
  }, []);

  const changeMember = (id: string) => {
    setApiMember(id);
    setMemberId(id);
  };
  const resetDemo = async () => {
    await post("/demo/reset");
  };
  const member = members.find((item) => item.id === memberId);
  const session = useMemo(
    () => member ? { members, member, changeMember, resetDemo } : null,
    [members, member]
  );
  if (bootError) return <div className="boot-error"><ErrorNotice message={bootError} /></div>;
  if (!session) return <Loading />;
  return (
    <SessionContext.Provider value={session}>
      <AppShell>
        <Routes key={memberId}>
          <Route path="/" element={<HomePage />} />
          <Route path="/projects/:projectId" element={<ProjectPage />} />
          <Route path="/tasks/:taskId" element={<TaskPage />} />
          <Route path="/tasks/:taskId/generate" element={<GeneratePage />} />
          <Route path="/tasks/:taskId/drafts/:draftId" element={<DraftPage />} />
          <Route path="/tasks/:taskId/handoff/new" element={<NewRequestPage />} />
          <Route path="/requests/:requestId" element={<RequestPage />} />
          <Route path="/tasks/:taskId/history" element={<HistoryPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </SessionContext.Provider>
  );
}

function PageHeader({
  eyebrow,
  title,
  description,
  back,
  actions
}: {
  eyebrow: string;
  title: string;
  description?: string;
  back?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        {back && <Link className="back-link" to={back}><ArrowLeft size={15} />返回</Link>}
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {description && <p className="lead">{description}</p>}
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </div>
  );
}

function HomePage() {
  const { member } = useSession();
  const { data, error, loading } = useLoad(
    () => api<{ items: Project[] }>("/projects"),
    [member.id]
  );
  return (
    <div className="page">
      <PageHeader
        eyebrow="团队任务责任链"
        title={"你好，" + member.display_name.split("（")[0]}
        description="从证据材料开始，经过人工审核和版本确认，再由接手者主动完成责任转移。"
      />
      <section className="flow-strip" aria-label="交接流程">
        {[
          ["01", "收集材料", "版本与来源可回看"],
          ["02", "整理草稿", "AI 可选，人工可替代"],
          ["03", "人工确认", "固定五项交接版本"],
          ["04", "主动接收", "接手者决定责任转移"]
        ].map(([no, title, text], index) => (
          <div className="flow-step" key={no}>
            <span>{no}</span><div><strong>{title}</strong><small>{text}</small></div>
            {index < 3 && <ChevronRight size={17} aria-hidden />}
          </div>
        ))}
      </section>
      <div className="section-heading">
        <div><p className="eyebrow">可访问范围</p><h2>你的项目</h2></div>
      </div>
      <ErrorNotice message={error} />
      {loading && <Loading />}
      <div className="project-list">
        {data?.items.map((project) => (
          <Link className="project-row" to={"/projects/" + project.id} key={project.id}>
            <span className="project-index">PR</span>
            <span className="project-copy">
              <strong>{project.name}</strong>
              <small>{project.description}</small>
            </span>
            <span className="role-tag">{project.role === "owner" ? "负责人" : "成员"}</span>
            <ArrowRight size={18} aria-hidden />
          </Link>
        ))}
      </div>
      {!loading && data?.items.length === 0 && <Empty>当前身份没有获准项目。</Empty>}
    </div>
  );
}

function ProjectPage() {
  const { projectId = "" } = useParams();
  const { member } = useSession();
  const { data, error, loading, reload } = useLoad(
    () => api<Project>("/projects/" + projectId),
    [projectId, member.id]
  );
  const [showForm, setShowForm] = useState(false);
  const [formError, setFormError] = useState("");
  const createTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError("");
    const values = new FormData(event.currentTarget);
    try {
      await post("/projects/" + projectId + "/tasks", {
        title: values.get("title"),
        goal: values.get("goal"),
        description: values.get("description"),
        acceptance_criteria: values.get("acceptance_criteria"),
        owner_id: member.id,
        progress: "not_started"
      });
      setShowForm(false);
      reload();
    } catch (reason) {
      setFormError((reason as ApiError).message);
    }
  };
  if (loading) return <div className="page"><Loading /></div>;
  if (!data) return <div className="page"><ErrorNotice message={error} /></div>;
  return (
    <div className="page">
      <PageHeader
        back="/"
        eyebrow="项目工作区"
        title={data.name}
        description={data.description}
        actions={
          <button className="button primary" onClick={() => setShowForm(!showForm)}>
            <Plus size={17} />创建任务
          </button>
        }
      />
      <div className="project-meta">
        <div><Users size={18} /><span><strong>{data.members?.filter((item) => item.active).length}</strong> 名有效成员</span></div>
        <div className="member-stack">
          {data.members?.filter((item) => item.active).map((item) => (
            <span key={item.member_id} title={item.display_name}>{item.display_name.slice(0, 1)}</span>
          ))}
        </div>
      </div>
      {showForm && (
        <form className="form-panel" onSubmit={createTask}>
          <div className="form-title"><h2>新建任务</h2><p>目标与验收标准用于确定交接边界。</p></div>
          <label>任务标题<input name="title" required minLength={2} /></label>
          <label>目标<textarea name="goal" required rows={2} /></label>
          <label>说明<textarea name="description" rows={2} /></label>
          <label>可验证的验收标准<textarea name="acceptance_criteria" required rows={3} /></label>
          <ErrorNotice message={formError} />
          <div className="form-actions">
            <button type="button" className="button ghost" onClick={() => setShowForm(false)}>取消</button>
            <button className="button primary">保存任务</button>
          </div>
        </form>
      )}
      <div className="section-heading"><div><p className="eyebrow">责任与状态</p><h2>任务列表</h2></div></div>
      <div className="task-table" role="table" aria-label="项目任务">
        <div className="task-row task-head" role="row">
          <span>任务</span><span>负责人</span><span>工作进度</span><span>内容审核</span><span>交接</span><span />
        </div>
        {data.tasks?.map((task) => (
          <Link className="task-row" role="row" to={"/tasks/" + task.id} key={task.id}>
            <span data-label="任务"><small>{task.display_no}</small><strong>{task.title}</strong></span>
            <span data-label="负责人">{task.owner_name}</span>
            <Status tone="blue" text={progressLabels[task.progress]} />
            <Status tone="amber" text={reviewLabels[task.review_state]} />
            <Status tone="teal" text={requestLabels[task.request_state]} />
            <ArrowRight size={17} aria-hidden />
          </Link>
        ))}
      </div>
      {data.tasks?.length === 0 && <Empty>还没有任务，先建立一个清楚的目标。</Empty>}
    </div>
  );
}

function Status({ tone, text }: { tone: string; text: string }) {
  return <span className={"status " + tone}><span aria-hidden />{text}</span>;
}

function StatusTriplet({ task }: { task: Task }) {
  return (
    <section className="status-triplet" aria-label="任务状态">
      <div><small>工作进度</small><Status tone="blue" text={progressLabels[task.progress]} /></div>
      <div><small>内容审核</small><Status tone="amber" text={reviewLabels[task.review_state]} /></div>
      <div><small>交接处理</small><Status tone="teal" text={requestLabels[task.request_state]} /></div>
    </section>
  );
}

function TaskPage() {
  const { taskId = "" } = useParams();
  const { member } = useSession();
  const { data, error, loading, reload } = useLoad(
    () => api<Task>("/tasks/" + taskId),
    [taskId, member.id]
  );
  const [materialOpen, setMaterialOpen] = useState(false);
  const [materialError, setMaterialError] = useState("");
  const addMaterial = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    setMaterialError("");
    try {
      await post("/tasks/" + taskId + "/materials/text", {
        title: values.get("title"),
        source_note: values.get("source_note"),
        content: values.get("content")
      });
      setMaterialOpen(false);
      reload();
    } catch (reason) {
      setMaterialError((reason as ApiError).message);
    }
  };
  if (loading) return <div className="page"><Loading /></div>;
  if (!data) return <div className="page"><ErrorNotice message={error} /></div>;
  const isOwner = data.owner_id === member.id;
  const latestConfirmed = data.confirmed_handoffs?.[0];
  return (
    <div className="page">
      <PageHeader
        back={"/projects/" + data.project_id}
        eyebrow={data.display_no + " · 当前负责人 " + data.owner_name}
        title={data.title}
        actions={<Link className="button ghost" to={"/tasks/" + taskId + "/history"}><History size={17} />历史</Link>}
      />
      <StatusTriplet task={data} />
      <section className="brief-grid">
        <div><small>任务目标</small><p>{data.goal}</p></div>
        <div><small>验收标准</small><p>{data.acceptance_criteria}</p></div>
      </section>
      {isOwner ? (
        <section className="next-action">
          <div><p className="eyebrow">推荐下一步</p><h2>{latestConfirmed ? "发起正式交接" : "整理并审核交接内容"}</h2>
            <p>{latestConfirmed ? "已有确认版本，选择项目成员作为接手者。" : "选择材料生成五项草稿，或完全人工填写。"}</p>
          </div>
          <Link className="button primary" to={latestConfirmed ? "/tasks/" + taskId + "/handoff/new" : "/tasks/" + taskId + "/generate"}>
            {latestConfirmed ? <Send size={17} /> : <Sparkles size={17} />}
            {latestConfirmed ? "发起交接" : "整理交接"}
          </Link>
        </section>
      ) : data.pending_request_id ? (
        <section className="next-action">
          <div><p className="eyebrow">等待你的决定</p><h2>阅读确认版本并主动处理</h2><p>查看来源、未知事项与验收标准后再决定是否接收。</p></div>
          <Link className="button primary" to={"/requests/" + data.pending_request_id}><BookOpen size={17} />查看交接请求</Link>
        </section>
      ) : null}
      <div className="section-heading">
        <div><p className="eyebrow">可追溯输入</p><h2>任务材料</h2></div>
        {isOwner && <button className="button secondary" onClick={() => setMaterialOpen(!materialOpen)}><Plus size={16} />添加文本</button>}
      </div>
      {materialOpen && (
        <form className="form-panel compact" onSubmit={addMaterial}>
          <label>材料标题<input name="title" required /></label>
          <label>来源说明<input name="source_note" placeholder="例如：本地测试记录" /></label>
          <label>正文<textarea name="content" required rows={7} /></label>
          <ErrorNotice message={materialError} />
          <div className="form-actions">
            <button type="button" className="button ghost" onClick={() => setMaterialOpen(false)}>取消</button>
            <button className="button primary">保存材料</button>
          </div>
        </form>
      )}
      <div className="material-list">
        {data.materials?.map((material) => <MaterialRow material={material} key={material.id} />)}
      </div>
      {data.materials?.length === 0 && <Empty>还没有材料。导入开发记录、测试输出或链接。</Empty>}
      {data.drafts && data.drafts.length > 0 && (
        <>
          <div className="section-heading"><div><p className="eyebrow">审核中</p><h2>交接草稿</h2></div></div>
          <div className="draft-list">
            {data.drafts.map((draft) => (
              <Link key={draft.id} to={"/tasks/" + taskId + "/drafts/" + draft.id}>
                <ClipboardCheck size={18} /><span><strong>{draft.origin === "manual" ? "人工草稿" : "Demo AI 草稿"}</strong><small>修订 {draft.revision} · {fmt(draft.updated_at)}</small></span><ArrowRight size={16} />
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function MaterialRow({ material }: { material: Material }) {
  const [open, setOpen] = useState(false);
  const latest = material.versions.at(-1);
  return (
    <article className="material-row">
      <button className="material-main" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="material-no">{material.display_no}</span>
        <span><strong>{material.title}</strong><small>{material.source_note || "未填写来源说明"} · v{latest?.version_no}</small></span>
        {latest?.unread_body && <span className="unread">未读取正文</span>}
        <ChevronRight className={open ? "rotate" : ""} size={17} />
      </button>
      {open && (
        <div className="material-body">
          {latest?.content ? (
            <ol>
              {latest.content.split("\n").map((line, index) => <li key={index}><span>{line || " "}</span></li>)}
            </ol>
          ) : (
            <p><Link2 size={16} />仅保存链接：{latest?.url}</p>
          )}
        </div>
      )}
    </article>
  );
}

function GeneratePage() {
  const { taskId = "" } = useParams();
  const { member } = useSession();
  const navigate = useNavigate();
  const { data, error, loading } = useLoad(() => api<Task>("/tasks/" + taskId), [taskId, member.id]);
  const [selected, setSelected] = useState<string[]>([]);
  const [preview, setPreview] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const textVersions = data?.materials?.flatMap((material) => {
    const latest = material.versions.at(-1);
    return latest?.content ? [{ ...latest, material }] : [];
  }) ?? [];
  const createPreview = async () => {
    setActionError("");
    try {
      setPreview(await post("/tasks/" + taskId + "/generation-previews", { material_version_ids: selected }));
    } catch (reason) {
      setActionError((reason as ApiError).message);
    }
  };
  const generate = async (mode: string) => {
    setBusy(true);
    setActionError("");
    try {
      const draft = await post<Draft>("/generation-previews/" + preview.id + "/runs", { mode });
      navigate("/tasks/" + taskId + "/drafts/" + draft.id);
    } catch (reason) {
      setActionError((reason as ApiError).message);
      setBusy(false);
    }
  };
  const manual = async () => {
    const sections = Object.fromEntries(sectionMeta.map(([key]) => [key, ""])) as Sections;
    const draft = await post<Draft>("/tasks/" + taskId + "/drafts", { sections, citations: [] });
    navigate("/tasks/" + taskId + "/drafts/" + draft.id);
  };
  if (loading) return <div className="page"><Loading /></div>;
  if (!data) return <div className="page"><ErrorNotice message={error} /></div>;
  return (
    <div className="page narrow">
      <PageHeader back={"/tasks/" + taskId} eyebrow="输入范围控制" title="整理交接草稿" description="先选择材料，再完整预览将被整理的范围。链接正文不会被隐式读取。" />
      <div className="stepper"><span className={!preview ? "active" : "done"}>1 选择</span><i /><span className={preview ? "active" : ""}>2 预览确认</span><i /><span>3 人工审核</span></div>
      {!preview ? (
        <>
          <section className="selection-panel">
            <div className="selection-head"><h2>选择正文材料</h2><span>{selected.length} 项 · {textVersions.filter((item) => selected.includes(item.id)).reduce((sum, item) => sum + (item.content?.length ?? 0), 0)} 字符</span></div>
            {textVersions.map((item) => (
              <label className="check-row" key={item.id}>
                <input type="checkbox" checked={selected.includes(item.id)} onChange={(event) => setSelected(event.target.checked ? [...selected, item.id] : selected.filter((id) => id !== item.id))} />
                <span><strong>{item.material.display_no} · {item.material.title}</strong><small>v{item.version_no} · {item.content?.split("\n").length} 行</small></span>
              </label>
            ))}
          </section>
          <ErrorNotice message={actionError} />
          <div className="sticky-actions"><button className="button ghost" onClick={manual}>转为人工填写</button><button className="button primary" disabled={!selected.length} onClick={createPreview}>预览实际输入<ArrowRight size={17} /></button></div>
        </>
      ) : (
        <>
          <section className="preview-panel">
            <div className="notice info"><ShieldCheck size={18} /><span>以下内容是本次整理的完整输入，共 {preview.character_count} 字符。未选材料和链接正文不在其中。</span></div>
            <div className="preview-context"><small>任务目标</small><p>{preview.input_snapshot.task.goal}</p><small>验收标准</small><p>{preview.input_snapshot.task.acceptance_criteria}</p></div>
            {preview.input_snapshot.materials.map((material: any, index: number) => (
              <div className="preview-material" key={material.version_id}><small>正文材料 {index + 1}</small><pre>{material.content}</pre></div>
            ))}
          </section>
          <ErrorNotice message={actionError} />
          <div className="sticky-actions">
            <button className="button ghost" onClick={() => setPreview(null)}>返回修改</button>
            <button className="button secondary" disabled={busy} onClick={() => generate("error")}>模拟失败</button>
            <button className="button primary" disabled={busy} onClick={() => generate("normal")}>{busy ? <LoaderCircle className="spin" size={17} /> : <Sparkles size={17} />}确认并生成草稿</button>
          </div>
        </>
      )}
    </div>
  );
}

function DraftPage() {
  const { taskId = "", draftId = "" } = useParams();
  const { member } = useSession();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useLoad(() => api<Draft>("/drafts/" + draftId), [draftId, member.id]);
  const [sections, setSections] = useState<Sections | null>(null);
  const [saveState, setSaveState] = useState("");
  useEffect(() => { if (data) setSections(data.sections); }, [data]);
  const citationInputs = data?.citations.map((citation) => ({
    section: citation.section,
    material_version_id: citation.material_version_id,
    start_line: citation.start_line,
    end_line: citation.end_line,
    quote: citation.quote
  })) ?? [];
  const save = async () => {
    if (!data || !sections) return;
    setSaveState("正在保存…");
    try {
      await patch("/drafts/" + draftId, {
        sections,
        citations: citationInputs,
        expected_revision: data.revision
      });
      setSaveState("已保存");
      reload();
    } catch (reason) {
      setSaveState((reason as ApiError).message);
    }
  };
  const confirm = async () => {
    if (!data || !sections) return;
    setSaveState("正在确认…");
    try {
      const saved = await patch<Draft>("/drafts/" + draftId, {
        sections,
        citations: citationInputs,
        expected_revision: data.revision
      });
      await post("/drafts/" + draftId + "/confirm", { expected_revision: saved.revision });
      navigate("/tasks/" + taskId);
    } catch (reason) {
      setSaveState((reason as ApiError).message);
    }
  };
  if (loading || !sections) return <div className="page"><Loading /></div>;
  if (!data) return <div className="page"><ErrorNotice message={error} /></div>;
  return (
    <div className="page review-page">
      <PageHeader back={"/tasks/" + taskId} eyebrow={data.origin === "manual" ? "人工草稿" : "Demo AI 草稿 · 必须人工核对"} title="逐项审核交接内容" description="确认会固定任务背景、五项正文和引用；保存或查看不会代替确认。" />
      <div className="version-banner"><ClipboardCheck size={18} /><span>草稿修订 {data.revision}</span><span>{saveState || "尚未保存本次编辑"}</span></div>
      <div className="review-layout">
        <div className="editor-sections">
          {sectionMeta.map(([key, label, hint], index) => (
            <label className="section-editor" key={key}>
              <span className="section-number">{String(index + 1).padStart(2, "0")}</span>
              <span className="section-label"><strong>{label}</strong><small>{hint}</small></span>
              <textarea rows={5} value={sections[key]} onChange={(event) => setSections({ ...sections, [key]: event.target.value })} />
            </label>
          ))}
        </div>
        <aside className="evidence-panel">
          <div><p className="eyebrow">来源证据</p><h2>{data.citations.length} 条引用</h2></div>
          {data.citations.length ? data.citations.map((citation, index) => (
            <article key={citation.id ?? index}>
              <small>{citation.material_display_no} · v{citation.version_no} · 第 {citation.start_line} 行</small>
              <blockquote>{citation.quote}</blockquote>
            </article>
          )) : <Empty>人工草稿暂未添加引用。可继续确认，但应明确未知或未验证。</Empty>}
        </aside>
      </div>
      <div className="sticky-actions"><button className="button secondary" onClick={save}>保存草稿</button><button className="button primary" onClick={confirm}><CheckCircle2 size={17} />保存并人工确认</button></div>
    </div>
  );
}

function NewRequestPage() {
  const { taskId = "" } = useParams();
  const { member } = useSession();
  const navigate = useNavigate();
  const { data: task, loading } = useLoad(() => api<Task>("/tasks/" + taskId), [taskId, member.id]);
  const { data: project } = useLoad<Project | null>(
    () => task ? api<Project>("/projects/" + task.project_id) : Promise.resolve(null),
    [task?.project_id, member.id]
  );
  const [recipient, setRecipient] = useState("");
  const [error, setError] = useState("");
  if (loading || !task) return <div className="page"><Loading /></div>;
  const confirmed = task.confirmed_handoffs?.[0];
  const candidates = project?.members?.filter((item) => item.active && item.member_id !== member.id) ?? [];
  const submit = async () => {
    if (!confirmed || !recipient) return;
    try {
      const request = await post<RequestDetail>("/tasks/" + taskId + "/handoff-requests", { confirmed_handoff_id: confirmed.id, recipient_id: recipient });
      navigate("/requests/" + request.id);
    } catch (reason) {
      setError((reason as ApiError).message);
    }
  };
  if (!confirmed) return <Navigate to={"/tasks/" + taskId} replace />;
  return (
    <div className="page narrow">
      <PageHeader back={"/tasks/" + taskId} eyebrow="责任转移前的最后核对" title="发起交接请求" description="发起后负责人仍然不变。只有接手者主动接收，责任才会转移。" />
      <section className="confirmed-summary">
        <div className="version-stamp"><Check size={22} /><span><small>确认版本</small><strong>V{confirmed.version_no}</strong></span></div>
        <div><strong>{confirmed.task_snapshot.title}</strong><p>{confirmed.task_snapshot.acceptance_criteria}</p><small>由 {confirmed.confirmed_by_name} 于 {fmt(confirmed.confirmed_at)} 确认</small></div>
      </section>
      <EvidenceNotice state={confirmed.evidence_state ?? "current"} />
      <label className="recipient-select">指定接手者<select value={recipient} onChange={(event) => setRecipient(event.target.value)}><option value="">请选择项目内有效成员</option>{candidates.map((item) => <option key={item.member_id} value={item.member_id}>{item.display_name}</option>)}</select></label>
      <div className="notice info"><UserRoundCheck size={18} /><span>接手者将看到完整五项、验收标准、未知事项和来源，并可请求补充、拒绝或主动接收。</span></div>
      <ErrorNotice message={error} />
      <div className="sticky-actions"><Link className="button ghost" to={"/tasks/" + taskId}>取消</Link><button className="button primary" disabled={!recipient || confirmed.evidence_state !== "current"} onClick={submit}><Send size={17} />发起交接</button></div>
    </div>
  );
}

function RequestPage() {
  const { requestId = "" } = useParams();
  const { member } = useSession();
  const { data, error, loading, reload } = useLoad(() => api<RequestDetail>("/handoff-requests/" + requestId), [requestId, member.id]);
  const [reason, setReason] = useState("");
  const [actionError, setActionError] = useState("");
  const act = async (kind: "needs-info" | "reject" | "accept") => {
    if (!data) return;
    setActionError("");
    try {
      await post("/handoff-requests/" + requestId + "/" + kind, kind === "accept" ? { expected_revision: data.revision } : { expected_revision: data.revision, reason });
      reload();
    } catch (cause) {
      setActionError((cause as ApiError).message);
    }
  };
  if (loading) return <div className="page"><Loading /></div>;
  if (!data) return <div className="page"><ErrorNotice message={error} /></div>;
  const actionable = data.status === "pending" && data.recipient_id === member.id;
  return (
    <div className="page request-page">
      <PageHeader back={"/tasks/" + data.task_id} eyebrow={"交接请求 · " + requestLabels[data.status]} title={data.task.title} description={"由 " + data.sender_name + " 发给 " + data.recipient_name} />
      <div className={"request-banner " + data.status}>
        {data.status === "accepted" ? <CheckCircle2 size={21} /> : <BookOpen size={21} />}
        <span><strong>{requestLabels[data.status]}</strong><small>{data.status === "pending" ? "阅读完整内容后，由你决定是否接收。" : data.reason || (data.receipt ? "责任已完成转移。" : "该请求已结束。")}</small></span>
      </div>
      <StatusTriplet task={{ ...data.task, request_state: data.status }} />
      <EvidenceNotice state={data.confirmed_handoff.evidence_state ?? "current"} />
      <section className="request-context"><div><small>任务目标</small><p>{data.confirmed_handoff.task_snapshot.goal}</p></div><div><small>验收标准</small><p>{data.confirmed_handoff.task_snapshot.acceptance_criteria}</p></div></section>
      <div className="handoff-sections">
        {sectionMeta.map(([key, label], index) => (
          <section key={key}><span>{String(index + 1).padStart(2, "0")}</span><div><h2>{label}</h2><p>{data.confirmed_handoff.sections[key]}</p>{data.confirmed_handoff.citations.filter((item) => item.section === key).map((item) => <blockquote key={item.id}>{item.material_display_no} · 第 {item.start_line} 行：{item.quote}</blockquote>)}</div></section>
        ))}
      </div>
      {actionable && (
        <section className="decision-panel">
          <div><p className="eyebrow">你的决定</p><h2>责任不会因浏览页面而改变</h2></div>
          <label>补充或拒绝原因<textarea rows={3} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="请求补充或拒绝时必须说明原因" /></label>
          <ErrorNotice message={actionError} />
          <div className="decision-actions">
            <button className="button ghost danger" disabled={reason.trim().length < 2} onClick={() => act("reject")}>拒绝接收</button>
            <button className="button secondary" disabled={reason.trim().length < 2} onClick={() => act("needs-info")}>请求补充</button>
            <button className="button primary" disabled={data.confirmed_handoff.evidence_state !== "current"} onClick={() => act("accept")}><UserRoundCheck size={17} />主动接收任务</button>
          </div>
        </section>
      )}
    </div>
  );
}

function HistoryPage() {
  const { taskId = "" } = useParams();
  const { member } = useSession();
  const task = useLoad(() => api<Task>("/tasks/" + taskId), [taskId, member.id]);
  const history = useLoad(() => api<{ items: TaskEvent[] }>("/tasks/" + taskId + "/history"), [taskId, member.id]);
  if (task.loading || history.loading) return <div className="page"><Loading /></div>;
  return (
    <div className="page narrow">
      <PageHeader back={"/tasks/" + taskId} eyebrow="不可改写的业务事件" title="任务历史" description={task.data?.title} />
      <div className="timeline">
        {history.data?.items.map((event, index) => (
          <article key={event.id}>
            <span className="timeline-dot">{event.seq ?? index + 1}</span>
            <div><small>{fmt(event.created_at)} · {event.actor_name}</small><h2>{eventLabel(event.event_type)}</h2><div className="event-badges"><span>{event.status}</span><span>{event.lifecycle}</span><span>{event.source}</span></div><p>{String(event.details.reason ?? "事件已记录并绑定对应业务版本。")}</p><code>{event.event_ref ?? event.id} · {event.entity_type} · {event.entity_id.slice(0, 8)}</code>{event.parent_event_ref && <small className="event-link">父事件：{event.parent_event_ref}</small>}{event.correlation_id && <small className="event-link">关联：{event.correlation_id}</small>}</div>
          </article>
        ))}
      </div>
      {history.data?.items.length === 0 && <Empty>暂无历史事件。</Empty>}
    </div>
  );
}

function eventLabel(value: string) {
  const labels: Record<string, string> = {
    task_created: "创建任务",
    task_updated: "更新任务",
    material_added: "添加材料",
    material_version_added: "更新材料版本",
    draft_generated: "生成交接草稿",
    draft_created: "创建人工草稿",
    draft_saved: "保存草稿",
    handoff_confirmed: "人工确认交接版本",
    handoff_requested: "发起交接请求",
    handoff_needs_info: "请求补充",
    handoff_rejected: "拒绝接收",
    handoff_expired: "旧请求失效",
    handoff_accepted: "主动接收并转移责任"
  };
  return labels[value] ?? value;
}
