import { motion } from 'framer-motion'
import {
  Compass, Fingerprint, GitBranch, Radar, Grid3X3, Network, Dices,
  Map, ShieldCheck, Scale, TrendingUp, ExternalLink, BookOpen,
} from 'lucide-react'
import { staggerContainer, fadeUp } from '@/utils/animation'

/*
 * Static methodology register: every method the pipeline uses, its literature
 * source(s), and the reason it is applied THE WAY it is here. No backend data —
 * the content mirrors the sprint-5 report (§ Theoretical Foundation + References)
 * and METHODOLOGY.md (Key Design Decisions). Figures are our own pipeline outputs.
 */

const GROUPS = [
  {
    title: 'Foundations',
    color: '#3b82f6',
    methods: [
      {
        icon: Compass,
        name: 'Exploratory scenario planning',
        what: 'The pipeline sits in the tradition of exploratory scenario planning: lay out several internally consistent, plausible futures instead of one forecast, to support decisions under deep uncertainty.',
        refs: [
          { authors: 'Schwartz, P.', year: 1991, title: 'The Art of the Long View', venue: 'Doubleday' },
          { authors: 'Kosow, H., & Gaßner, R.', year: 2008, title: 'Methods of Future and Scenario Analysis', venue: 'German Development Institute (DIE)' },
          { authors: 'Amer, M., Daim, T. U., & Jetter, A.', year: 2013, title: 'A review of scenario planning', venue: 'Futures, 46, 23–40', href: 'https://doi.org/10.1016/j.futures.2012.10.003' },
        ],
        why: 'A 2035 horizon cannot be predicted, only spanned. Everything downstream (morphological box, CIB, archetypes) exists to keep that span internally consistent rather than arbitrary.',
      },
      {
        icon: Fingerprint,
        name: 'Retrieval-augmented generation & traceability',
        what: 'Every generative step draws on retrieved source passages instead of free association: focused RAG with 3–5 chunks per call, lean prompts.',
        refs: [
          { authors: 'Lewis, P., et al.', year: 2020, title: 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks', venue: 'NeurIPS', href: 'https://arxiv.org/abs/2005.11401' },
        ],
        why: 'Nothing is invented: every driver, coupling and narrative keeps its source-chunk IDs for life. That makes each claim auditable back to a paragraph in the corpus, and it is what lets the whole framework dock onto a different knowledge base.',
      },
    ],
  },
  {
    title: 'Driver identification',
    color: '#0ea5e9',
    methods: [
      {
        icon: GitBranch,
        name: 'Bill-of-materials decomposition',
        what: 'The product is recursively decomposed into its component tree (engineering BOM practice), with an LLM classifying which leaves are active technology drivers, each citing the datasheet chunks that support it.',
        refs: [
          { authors: 'Component-first product decomposition', year: null, title: 'Engineering practice; LLM-assisted, evidence-cited per node', venue: 'internal design' },
        ],
        why: 'The BOM defines what the product already covers. It is deliberately the reference, not the output: external drivers are found by looking at everything the BOM does NOT explain.',
      },
      {
        icon: Radar,
        name: 'Coverage-gap trend scanning',
        what: 'All trend-pool chunks are embedded; chunks with low cosine similarity to every BOM driver are “orphans”. Orphans are bucketed to their nearest driving dimension (regulatory / market / geopolitical / technological) and clustered per bucket with k-means; one focused LLM call names each cluster.',
        refs: [
          { authors: 'Embedding-space coverage gap + per-dimension k-means', year: null, title: 'No hardcoded search queries: the KB itself decides what is a trend', venue: 'internal design' },
        ],
        why: 'Hardcoded queries would smuggle the domain into the pipeline. The coverage-gap formulation is KB-agnostic, and dimension bucketing prevents one loud theme from collapsing the driver set into a monoculture.',
      },
    ],
  },
  {
    title: 'Scenario construction',
    color: '#8b5cf6',
    methods: [
      {
        icon: Grid3X3,
        name: 'Morphological analysis (Zwicky box)',
        what: 'A small set of drivers, each with a few ordered future states, whose combinations span the space of futures: 14 drivers × 4 manifestations = 268,435,456 combinations.',
        refs: [
          { authors: 'Zwicky, F.', year: 1969, title: 'Discovery, Invention, Research Through the Morphological Approach', venue: 'Macmillan' },
          { authors: 'Ritchey, T.', year: 2011, title: 'Wicked Problems / Social Messes: Decision Support Modelling with Morphological Analysis', venue: 'Springer', href: 'https://doi.org/10.1007/978-3-642-19653-9' },
        ],
        why: 'Manifestations are kept ORDINAL (optimistic → pessimistic), not just categorical. Downstream analysis exploits that order: the ordinal encoding is what later makes the archetype structure visible at all.',
      },
      {
        icon: Network,
        name: 'Cross-Impact Balance (CIB)',
        what: 'For each pair of driver states a judgment records whether one promotes or inhibits the other; consistent scenarios are those with low internal tension. The matrix is elicited from a panel of five LLM expert personas over two Delphi-style rounds.',
        refs: [
          { authors: 'Weimer-Jehle, W.', year: 2006, title: 'Cross-impact balances: A system-theoretical approach to cross-impact analysis', venue: 'Technological Forecasting and Social Change, 73(4), 334–361', href: 'https://doi.org/10.1016/j.techfore.2005.06.005' },
          { authors: 'Sharma, M., et al.', year: 2023, title: 'Towards Understanding Sycophancy in Language Models', venue: 'arXiv:2310.13548', href: 'https://arxiv.org/abs/2310.13548' },
        ],
        why: 'LLMs carry a documented positivity / sycophancy bias that erases trade-offs. The panel therefore scores promoting and inhibiting effects separately and PRESERVES dissent in aggregation, restoring the ~20–30% inhibiting share Weimer-Jehle reports for real systems (ours: 22%).',
        fig: { src: '/static/methods/cib_matrix.png', caption: 'Our elicited 14×14 CIB matrix (own pipeline output).' },
      },
      {
        icon: Dices,
        name: 'Two routes to scenarios: fixed points & sampled field',
        what: 'Route A: classic Weimer-Jehle fixed-point scenarios (perfect equilibria). Route B: combinatorial soft-CIB sampling, a Monte-Carlo over the persona disagreement that keeps every configuration whose internal tension stays below a threshold (120 consistent scenarios).',
        refs: [
          { authors: 'Weimer-Jehle fixed points + Monte-Carlo soft sampling', year: null, title: 'Both routes computed and shown side by side', venue: 'internal design' },
        ],
        why: 'Equilibria alone hide the shape of the possibility space; a sampled field alone hides the attractors. Showing both is the honest answer, and the sampled field is what makes structure analysis meaningful.',
      },
    ],
  },
  {
    title: 'Structure, validation & evaluation',
    color: '#10b981',
    methods: [
      {
        icon: Map,
        name: 'Projection & clustering: UMAP, HDBSCAN, silhouette',
        what: 'Scenario configurations are projected with UMAP and PCA; cluster structure is judged with the silhouette coefficient under four lenses: one-hot vs. ordinal encoding × k-means vs. HDBSCAN.',
        refs: [
          { authors: 'McInnes, L., Healy, J., & Melville, J.', year: 2018, title: 'UMAP: Uniform Manifold Approximation and Projection for Dimension Reduction', venue: 'arXiv:1802.03426', href: 'https://arxiv.org/abs/1802.03426' },
          { authors: 'Campello, R. J. G. B., Moulavi, D., & Sander, J.', year: 2013, title: 'Density-based clustering based on hierarchical density estimates', venue: 'PAKDD, Springer', href: 'https://doi.org/10.1007/978-3-642-37456-2_14' },
          { authors: 'Rousseeuw, P. J.', year: 1987, title: 'Silhouettes: a graphical aid to the interpretation and validation of cluster analysis', venue: 'J. Comput. Appl. Math., 20, 53–65', href: 'https://doi.org/10.1016/0377-0427(87)90125-7' },
        ],
        why: 'K-means forces every point into a cluster, so it is paired with a density method that may honestly leave points unassigned. The lens choice (ordinal encoding + HDBSCAN) lifts the silhouette from 0.07 to 0.38 and yields 5 named archetypes plus a 33% continuum, reported as such.',
        fig: { src: '/static/methods/space_two_lenses_svg.png', caption: 'The same 120 scenarios under the k-means vs. HDBSCAN lens (own pipeline output).' },
      },
      {
        icon: ShieldCheck,
        name: 'Null-model referee & synthetic controls',
        what: 'Every structure claim is tested against a uniform-random null model (z-scores), and the whole engine is validated on synthetic fields: one with planted coupling (must detect) and one with zero coupling (must stay silent).',
        refs: [
          { authors: 'Permutation / null-model testing', year: null, title: 'Positive & negative synthetic controls for the scenario engine', venue: 'internal design' },
        ],
        why: 'The engine must not hallucinate clusters. Verdicts: planted coupling → silhouette 0.72, z = 8.6; zero coupling → z = −0.7; a flat result is a property of the data, so we fixed the data (corpus, CIB), never the verdict.',
        fig: { src: '/static/methods/silhouette_by_lens_svg.png', caption: 'Silhouette per lens vs. the 0.25 rule-of-thumb floor (own pipeline output).' },
      },
      {
        icon: Scale,
        name: 'Multi-criteria evaluation: AHP + TOPSIS',
        what: 'Scenario priorities come from the Analytic Hierarchy Process for criterion weights (pairwise comparisons, consistency ratio < 0.10) and TOPSIS for the ranking, fed with evidence-grounded scores.',
        refs: [
          { authors: 'Saaty, T. L.', year: 1980, title: 'The Analytic Hierarchy Process', venue: 'McGraw-Hill' },
          { authors: 'Hwang, C. L., & Yoon, K.', year: 1981, title: 'Multiple Attribute Decision Making: Methods and Applications (TOPSIS)', venue: 'Springer', href: 'https://doi.org/10.1007/978-3-642-48318-9' },
        ],
        why: 'A weighted sum hides trade-offs between criteria. TOPSIS measures distance to the ideal AND the anti-ideal solution, and risk severity enters as a cost criterion, so a scenario cannot buy its way out of high risk with one good score.',
      },
      {
        icon: TrendingUp,
        name: 'Signal maturity (DVI-style temporal track)',
        what: 'Per driver, evidence is placed on two temporal axes: visibility trend (recent vs. older evidence) and diffusion (breadth of distinct sources), plus a weak-signal test.',
        refs: [
          { authors: 'Document-vitality-index lineage', year: null, title: 'Two-axis evidence maturity instead of lifecycle curve fitting', venue: 'internal design (temporal track)' },
        ],
        why: 'Deliberately NOT logistic S-curve fitting: a small curated knowledge base is temporally far too sparse to fit lifecycles honestly. Trend slope and source breadth are the claims the data can actually support.',
      },
    ],
  },
]

function RefEntry({ r }) {
  const body = (
    <>
      <BookOpen size={13} className="mt-0.5 shrink-0 text-zinc-500 group-hover/ref:text-blue-400 transition-colors" />
      <span className="min-w-0 text-xs leading-relaxed text-zinc-400">
        {r.authors}{r.year ? ` (${r.year}).` : '.'} <span className="italic text-zinc-300">{r.title}</span>. {r.venue}.
      </span>
      {r.href && <ExternalLink size={12} className="mt-0.5 shrink-0 text-zinc-600 group-hover/ref:text-blue-400 transition-colors" />}
    </>
  )
  const cls = 'group/ref flex items-start gap-2 rounded-lg border border-white/[0.06] bg-zinc-900/60 px-3 py-2'
  return r.href ? (
    <a href={r.href} target="_blank" rel="noreferrer" className={`${cls} hover:border-blue-500/40 transition-colors`}>
      {body}
    </a>
  ) : (
    <div className={cls}>{body}</div>
  )
}

function MethodCard({ m, color }) {
  const Icon = m.icon
  return (
    <motion.div variants={fadeUp} className="glass rounded-xl p-5 flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <span
          className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
          style={{ backgroundColor: `${color}1a`, border: `1px solid ${color}40` }}
        >
          <Icon size={18} style={{ color }} />
        </span>
        <h3 className="text-base font-semibold text-white leading-snug">{m.name}</h3>
      </div>

      <p className="text-sm text-zinc-400 leading-relaxed">{m.what}</p>

      <div className="flex flex-col gap-1.5">
        {m.refs.map((r, i) => <RefEntry key={i} r={r} />)}
      </div>

      <div className="border-l-2 pl-3" style={{ borderColor: '#f59e0b99' }}>
        <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-300/90">Why this way</p>
        <p className="mt-1 text-sm text-zinc-300 leading-relaxed">{m.why}</p>
      </div>

      {m.fig && (
        <figure className="mt-1">
          <img
            src={m.fig.src}
            alt={m.fig.caption}
            loading="lazy"
            className="w-full rounded-lg border border-white/[0.08] bg-zinc-900"
          />
          <figcaption className="mt-1.5 text-[11px] text-zinc-500">{m.fig.caption}</figcaption>
        </figure>
      )}
    </motion.div>
  )
}

export default function MethodologyPage() {
  return (
    <motion.div
      variants={staggerContainer}
      initial="enter"
      animate="center"
      className="max-w-7xl mx-auto px-8 py-8 space-y-10"
    >
      <motion.div variants={fadeUp}>
        <h1 className="text-2xl font-bold text-white">Methodology</h1>
        <p className="text-sm text-zinc-400 mt-1 max-w-3xl">
          Every method in the pipeline, its literature source, and why it is applied the way it is here.
          Established foresight and decision methods, combined with current NLP: nothing bespoke where a
          method with a track record exists, and every deviation justified.
        </p>
      </motion.div>

      {GROUPS.map((g) => (
        <motion.section key={g.title} variants={fadeUp} className="space-y-4">
          <div className="flex items-center gap-2.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: g.color }} />
            <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-400">{g.title}</h2>
            <span className="flex-1 h-px bg-white/[0.06]" />
          </div>
          <motion.div variants={staggerContainer} className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
            {g.methods.map((m) => <MethodCard key={m.name} m={m} color={g.color} />)}
          </motion.div>
        </motion.section>
      ))}
    </motion.div>
  )
}
