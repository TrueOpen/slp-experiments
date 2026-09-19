#!/usr/bin/env python3
"""Build the public SLP experiment dataset from archived run logs.

Copies raw logs (ANSI colour codes stripped, local home paths redacted) into
raw/<group>/ and extracts machine-readable CSV tables into data/.
Run from the repository root:  python3 tools/build_dataset.py <archive_root>
where <archive_root> contains gpu-run-archive/, 70b-run-archive/ and the Mac logs.
"""
import csv, os, re, shutil, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(ROOT)
ANSI = re.compile(r'\x1b\[[0-9;]*m')

def clean(text):
    text = ANSI.sub('', text)
    text = re.sub(r'/Users/[A-Za-z0-9_.-]+', '/Users/<user>', text)
    return text

def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(src, errors='ignore') as f: t = f.read()
    with open(dst, 'w') as f: f.write(clean(t))
    return t

def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    print(f"  wrote {os.path.relpath(path, ROOT)} ({len(rows)} rows)")

raw = lambda *p: os.path.join(ROOT, 'raw', *p)
data = lambda *p: os.path.join(ROOT, 'data', *p)
G = os.path.join(SRC, 'gpu-run-archive'); S = os.path.join(SRC, '70b-run-archive')

# ---------- raw copies ----------
groups = {
 'mac-m3pro': ['layer_cost_results.txt','layer_cost_sweep.log','attn_cost_results.txt','attn_cost_sweep.log',
               'slp_demo_run.log','sampled_gpt2_test.log'],
}
for f in groups['mac-m3pro']:
    p = os.path.join(SRC, f)
    if os.path.exists(p): copy(p, raw('mac-m3pro', f))
for f in glob.glob(os.path.join(SRC, 'slp-experiments', 'raw', 'slp_demo_gpt2_mac_*.log')):
    shutil.move(f, raw('mac-m3pro', os.path.basename(f))) if os.path.dirname(f) != raw('mac-m3pro') else None
for f in sorted(glob.glob(os.path.join(G, '*'))):
    b = os.path.basename(f)
    if b in ('pip_install.log', 'cudabuild.log'): continue
    copy(f, raw('gpu-rtx4090', b))
for b in ['run70b_v2.log','run70b.log','smoke_tiny.log','config-Llama-2-70b.json','setup70b.log','dl70b.log','merge70b.log','build2.log']:
    p = os.path.join(S, b)
    if os.path.exists(p): copy(p, raw('cpu-2tb-70b', b))
print("raw copies done")

rd = lambda *p: clean(open(os.path.join(*p), errors='ignore').read())

# ---------- E03 / E04 cost sweeps ----------
rows = []
for m in re.finditer(r'LAYER_COST_CSV,(.+)', rd(SRC, 'layer_cost_results.txt')):
    kv = dict(x.split('=') for x in m.group(1).split(','))
    rows.append([kv[k] for k in ['d','seq','ffn_mult','params','build_s','run_s','setup_s','prove_s','verify_s','proof_kib']])
rss = re.findall(r'(\d+)\s+maximum resident set size', rd(SRC, 'layer_cost_results.txt'))
for r, m in zip(rows, rss): r.append(round(int(m)/2**30, 2))
write_csv(data('E03_single_layer_cost_ffn.csv'), ['d_model','seq_len','ffn_mult','params','build_s','run_s','setup_s','prove_s','verify_s','proof_kib','peak_rss_gib'], rows)
rows = []
for m in re.finditer(r'ATTN_COST_CSV,(.+)', rd(SRC, 'attn_cost_results.txt')):
    kv = dict(x.split('=') for x in m.group(1).split(','))
    rows.append([kv['seq'], kv['kind'], kv['chunk'], kv['run_s'], kv['prove_s'], kv['proof_kib']])
write_csv(data('E04_attention_vs_mlp_chunk_cost_gpt2.csv'), ['seq_len','chunk_kind','chunk_id','run_s','prove_s','proof_kib'], rows)

# ---------- E02 70B stages ----------
t = rd(S, 'run70b_v2.log'); rows = []
for m in re.finditer(r'\[stage\] (\d/\d) (.+?) ✓\s+用时 ([0-9.]+)s', t):
    rows.append([m.group(1), m.group(2).strip(), m.group(3)])
extra = {'sealed_chunks': re.search(r'封存 (\d+) 层, 证明其中 (\d+) 层', t), 'proof': re.search(r'证明大小 ([0-9.]+ [KM]iB)', t), 'total': re.search(r'总用时 ([0-9.]+)s', t)}
rows.append(['-', 'total', extra['total'].group(1)])
write_csv(data('E02_llama2_70b_stages.csv'), ['stage','description','elapsed_s'], rows)
with open(data('E02_llama2_70b_summary.txt'), 'w') as f:
    f.write(f"sealed_chunks={extra['sealed_chunks'].group(1)} proven_chunks={extra['sealed_chunks'].group(2)} proof_size={extra['proof'].group(1)} total_s={extra['total'].group(1)}\n")
    f.write("peak_memory: load+quantize 387 GB resident; streaming weight commitment ~60 GB working set; whole pipeline < 2 TB (host limit). Source: operator notes, streaming-refactor-plan.md\n")

# ---------- E05 packing ----------
rows = []
for b, f in [(3,'gpu_packed.log'),(6,'gpu_packed_b6.log'),(12,'gpu_packed_b12.log')]:
    t = rd(G, f)
    prove = re.search(r'一份证明覆盖全部槽位） ✓\s+用时 ([0-9.]+)s', t).group(1)
    size = re.search(r'证明大小 ([0-9.]+) MiB', t).group(1)
    ver = re.search(r'解码绑定 ✓\s+用时 ([0-9.]+)s', t).group(1)
    inf = re.search(r'打包推理（锁步解码） ✓\s+用时 ([0-9.]+)s', t).group(1)
    sep = re.findall(r'单独证明 prompt \[\d\] ✓\s+用时 ([0-9.]+)s', t)
    rows.append([b, 16, 4, 2, inf, prove, size, ver, ';'.join(sep) if sep else '', sum(map(float,sep)) if sep else ''])
write_csv(data('E05_packed_batch_proving_tinyllama.csv'), ['batch_B','slot_len','gen_tokens_per_slot','samples_s','packed_inference_s','packed_prove_s','proof_mib','verify_s','separate_prove_s_each','separate_prove_s_total'], rows)
t = rd(G, 'gpu_leak.log'); leak = re.findall(r'槽位 (\d) (✓ 不变|✗ .+?)\s', t)
t2 = rd(G, 'gpu_equiv.log'); eq = re.findall(r'\[(\d)\] (✓ 一致|✗ 不一致)', t2)
write_csv(data('E05_packed_leak_and_equivalence_checks.csv'), ['check','slot','result'], [['leak_check_swap_neighbours', s, r] for s, r in leak] + [['equivalence_vs_single_prompt', s, r] for s, r in eq])

# ---------- E06 service ----------
t = rd(G, 'gpu_service_llmobs.log'); rows = []
for m in re.finditer(r'^\s+(\d) \|\s+(\d+) \|\s+(\d+) \|\s+([0-9.]+) \|\s+([0-9.]+) \|\s+([0-9.]+) \|\s+(\d+) \|\s+(\d+/\d+) \| (.+)$', t, re.M):
    rows.append(list(m.groups()))
write_csv(data('E06_service_simulation_tinyllama.csv'), ['window','requests','tokens','decode_s','prove_s','verify_s','proof_kib','proven_over_sealed','result'], rows)

# ---------- E07 fidelity (generation-level) ----------
rows = []
for f, tag in [('gpu_fid_final.log','after_fix'),('gpu_fid_bits12.log','before_fix_generic_observer'),('gpu_fid_after_fix.log','after_fix_rerun')]:
    t = rd(G, f)
    for m in re.finditer(r'^\s*(\S.*?) \|\s+(\d+)% \|\s+(\d+)% \|\s+(\d+)%(?: \|\s+(\d+)%)? \|\s+(\d+)s\s*$', t, re.M):
        rows.append([tag, m.group(1).strip(), m.group(2), m.group(3), m.group(4), m.group(5) or '', m.group(6)])
write_csv(data('E07_fidelity_generation_16prompts_tinyllama.csv'), ['run','calibration_config','first_token_match_pct','per_token_match_pct','full_sentence_match_pct','teacher_forced_match_pct','quantize_s'], rows)

# ---------- E08 early corpus eval (train split, superseded) ----------
t = rd(G, 'gpu_corpus_eval.log'); rows = []
for m in re.finditer(r'^\s*(\S.*?) \| ([0-9.]+) \| ([0-9.]+)% \| ([0-9.]+)% \| ([0-9.]+)% \| ([0-9.]+) \| (\S+)\s*$', t, re.M):
    rows.append(list(m.groups()))
write_csv(data('E08_wikitext2_train_1984pos_superseded.csv'), ['model','ppl','top1_hit_pct','argmax_agree_f32_pct','top5_overlap_pct','kl_f32_q_nats','quantize_s'], rows)

# ---------- E09 WikiText-2 test, per-window cumulative ----------
t = rd(G, 'gpu_std_eval.log'); rows = []
for m in re.finditer(r'\[(\w+)\] 窗口 (\d+)/655\s+(\d+)s\s+累计: 预测位 (\d+)\s+f32 PPL ([0-9.]+) / top-1 ([0-9.]+)%\s+\|\s+量化 PPL ([0-9.]+) / top-1 ([0-9.]+)%\s+与 f32 一致 ([0-9.]+)%\s+top-5 重叠 ([0-9.]+)%\s+KL ([0-9.]+) nat', t):
    rows.append(list(m.groups()))
write_csv(data('E09_wikitext2_test_cumulative_by_window.csv'), ['calibration','window','elapsed_s','positions','f32_ppl','f32_top1_pct','q_ppl','q_top1_pct','argmax_agree_pct','top5_overlap_pct','kl_nats'], rows)
rows = []
for m in re.finditer(r'^\s*(\S.*?) \| ([0-9.]+) \| ([0-9.]+)% \| ([0-9.]+)% \| ([0-9.]+)% \| ([0-9.]+)\s*$', t, re.M):
    rows.append(list(m.groups()))
write_csv(data('E09_wikitext2_test_summary.csv'), ['model','ppl','top1_hit_pct','argmax_agree_f32_pct','top5_overlap_pct','kl_f32_q_nats'], rows)

# ---------- E10 full vs sampled ----------
t = rd(G, 'gpu_full_vs_sampled.log'); rows = []
for m in re.finditer(r'SAMPLES=(\d+)\) ✓\s+用时 ([0-9.]+)s\s+→ 封存 (\d+) 层, 证明其中 (\d+) 层\s+→ 证明大小 ([0-9.]+ [KM]iB).*?验证\(SAMPLES=\d+\) ✓\s+用时 ([0-9.]+)s', t, re.S):
    rows.append(list(m.groups()))
rows.append(['upstream_single_chunk_full', 'did not complete: prover stack overflow (exit 134)', '', '', '', ''])
write_csv(data('E10_full_vs_sampled_tinyllama.csv'), ['samples_s','seal_and_prove_s','sealed_chunks','proven_chunks','proof_size','verify_s'], rows)

# ---------- E11 determinism ----------
rows = []
for i in range(1, 11):
    t = rd(G, f'gpu_det_{i}.log')
    m = re.search(r'校准 digest (\w+)…\s+量化权重指纹 (\w+)…\s+激活缩放指纹 (\w+)…', t)
    reps = re.findall(r'推理重复 #(\d)：(.+)', t)
    rows.append([i, m.group(1), m.group(2), m.group(3)] + [('match' if '一致' in r and '不' not in r else 'mismatch') for _, r in reps])
write_csv(data('E11_determinism_10_registrations.csv'), ['run','calibration_digest_prefix','weight_fingerprint_prefix','activation_scale_fingerprint_prefix','repeat1','repeat2'], rows)

# ---------- E12 grinding ----------
rows = []
for f in ['grind_gpt2.log','grind_syn_26_26.log']:
    t = rd(G, f)
    for m in re.finditer(r'GRIND_ROW label=(\S+) M=(\d+) s=(\d+) b=(\d+) coverage=([0-9.]+) q=([0-9.]+) theory_trials=([0-9.]+) mean_trials=([0-9.]+) max_trials=(\d+) reps=(\d+) per_trial_ms=([0-9.]+)', t):
        g = list(m.groups()); b = re.search(rf'BEACON_ROW label={g[0]} M={g[1]} s={g[2]} b={g[3]} beacons=(\d+) escape_frac=([0-9.]+)', t)
        rows.append(g + [b.group(1), b.group(2)])
write_csv(data('E12_grinding_attack_and_beacon.csv'), ['label','M_nonanchor_chunks','samples_s','fabricated_b','coverage','q_escape_prob','theory_mean_trials','measured_mean_trials','max_trials','reps','per_trial_ms','beacons_tested','beacon_escape_frac'], rows)

# ---------- E04b proving-stage breakdown from the profiling run ----------
import collections
t = rd(G, 'gpu_profile.log'); agg = collections.Counter()
for m in re.finditer(r'== (.+?) metrics elapsed=([0-9.]+)(ms|s|µs|us)', t):
    v = float(m.group(2)); u = m.group(3)
    agg[m.group(1).strip()] += v/1000 if u == 'ms' else (v/1e6 if u in ('µs','us') else v)
tot = sum(agg.values())
write_csv(data('E04b_proving_stage_breakdown_tinyllama_ctx8.csv'), ['stage_label','total_s','share_pct'], [[k, round(v, 2), round(100*v/tot, 1)] for k, v in agg.most_common()])

# ---------- E01 GPT-2 demo (latest local run if present) ----------
demo = sorted(glob.glob(raw('mac-m3pro', 'slp_demo_gpt2_mac_*.log')))
if demo:
    t = rd(demo[-1]); rows = []
    for m in re.finditer(r'\[worker\]\s+(prompt|inference|seal \+ prove|receipt|proof size)\s*:\s*(.+)', t):
        rows.append(['worker', m.group(1).strip(), m.group(2).strip()])
    for m in re.finditer(r'\[verifier\]\s+(.+?)\s*\.{2,}\s*(ACCEPT|REJECT|ADMITTED)\s*[✓⚠]\s*(\(.*?\))?', t):
        rows.append(['verifier', m.group(1).strip(), (m.group(2) + ' ' + (m.group(3) or '')).strip()])
    write_csv(data('E01_gpt2_demo_mac_latest.csv'), ['role','item','value'], rows)
print("done")
