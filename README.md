# SLP Proof-of-Concept Experiment Data

Raw run logs and extracted data tables for the proof-of-concept phase of SLP (Sampled Layerwise Proofs), a verifiable-inference protocol for large language models, August–September 2026. The accompanying experiment report is `REPORT.md`.

## Layout

```
raw/                 raw run logs (terminal colour codes stripped, local user paths redacted; otherwise verbatim)
  mac-m3pro/         laptop CPU (Apple M3 Pro, 18 GB): GPT-2 end-to-end demo, single-layer and attention cost sweeps, protocol tests
  gpu-rtx4090/       GPU server (RTX 4090 24 GB, host 2x AMD EPYC 7742, 1 TB RAM): all TinyLlama-1.1B experiments
  cpu-2tb-70b/       CPU server (256 threads, 2 TB RAM, 1.6 TB local disk): Llama-2-70B end to end
data/                CSV tables extracted from raw/ (column descriptions below), ready for plotting
tools/build_dataset.py  rebuilds raw/ and data/ from the archived logs
```

## Experiment index

| ID | Experiment | Platform | Data table | Raw log |
|---|---|---|---|---|
| E01 | GPT-2 end to end: sealing, sampled proof, verification, tamper rejection, tolerance check | Mac | `E01_gpt2_demo_mac_latest.csv` | `mac-m3pro/slp_demo_gpt2_mac_2026-09-17.log` (older run of 2026-08-28: `slp_demo_run.log`) |
| E02 | Llama-2-70B end to end, five stages | CPU 2 TB | `E02_llama2_70b_stages.csv`, `E02_llama2_70b_summary.txt` | `cpu-2tb-70b/run70b_v2.log` (failed first attempt: `run70b.log`) |
| E03 | Synthetic feed-forward block cost sweep, d = 256 to 4096 | Mac | `E03_single_layer_cost_ffn.csv` | `mac-m3pro/layer_cost_results.txt` |
| E04 | GPT-2 attention vs. MLP chunk proving cost against sequence length | Mac | `E04_attention_vs_mlp_chunk_cost_gpt2.csv` | `mac-m3pro/attn_cost_results.txt` |
| E04b | TinyLlama proving-stage time breakdown (context 8) | GPU box | `E04b_proving_stage_breakdown_tinyllama_ctx8.csv` | `gpu-rtx4090/gpu_profile.log` |
| E05 | Packed batch proving B = 3/6/12; leak check; equivalence check | GPU box | `E05_packed_batch_proving_tinyllama.csv`, `E05_packed_leak_and_equivalence_checks.csv` | `gpu-rtx4090/gpu_packed*.log`, `gpu_leak.log`, `gpu_equiv.log` |
| E06 | Verifiable inference service simulation (12 requests, 3 windows, tampering scenario) | GPU box | `E06_service_simulation_tinyllama.csv` | `gpu-rtx4090/gpu_service_llmobs.log` |
| E07 | Quantization fidelity, generation level (16 prompts): observer and calibration configurations | GPU box | `E07_fidelity_generation_16prompts_tinyllama.csv` | `gpu-rtx4090/gpu_fid_*.log` |
| E08 | Early corpus evaluation (WikiText-2 train, 1,984 positions), superseded by E09 | GPU box | `E08_wikitext2_train_1984pos_superseded.csv` | `gpu-rtx4090/gpu_corpus_eval.log` |
| E09 | Standard-corpus fidelity (WikiText-2 test, 655 windows x 512 tokens, 334,705 positions) | GPU box | `E09_wikitext2_test_summary.csv`, `E09_wikitext2_test_cumulative_by_window.csv` | `gpu-rtx4090/gpu_std_eval.log` |
| E10 | Full vs. sampled proof on the same trace, s = 0/2/5/10/all | GPU box | `E10_full_vs_sampled_tinyllama.csv` | `gpu-rtx4090/gpu_full_vs_sampled.log` |
| E11 | Determinism: fingerprints of 10 independent registrations and in-process repeated inference | GPU box | `E11_determinism_10_registrations.csv` | `gpu-rtx4090/gpu_det_1..10.log` |
| E12 | Grinding attack measurement and beacon fix (GPT-2 and synthetic model) | Mac | `E12_grinding_attack_and_beacon.csv` | `gpu-rtx4090/grind_gpt2.log`, `grind_syn_26_26.log` (run on the Mac, archived here) |

Other logs: `gpu-rtx4090/gpu_tiny.log`, `gpu_tiny2.log`, `gpu_ctx16.log` (TinyLlama GPU inference before/after the lookup optimization and context 8 vs. 16), `gpu_profile_infer_summary.txt` (inference operator time breakdown), `gpu_fid_dbg.log` (fidelity debugging), `gpu_followup.log` (scheduler log of E10/E11, including the exit code of the crashed upstream baseline in E10).

## Platforms

| Label | Hardware | Use |
|---|---|---|
| Mac | Apple M3 Pro, 18 GB unified memory, CPU only | GPT-2 (124M, Q8_0) end to end; synthetic layer cost sweeps; grinding experiments |
| GPU box | NVIDIA RTX 4090 24 GB; host 2x AMD EPYC 7742 (128 cores / 256 threads), 1007 GB RAM; Ubuntu 24.04, CUDA 12.8 | TinyLlama-1.1B-Chat-v1.0: inference and calibration on the GPU, **proving and verification on the host CPU** |
| CPU 2 TB | 256-thread CPU server, 2 TB RAM, 1.6 TB local disk (CPU model not recorded) | Llama-2-70B end to end (single-threaded integer inference) |

## Column notes for the main tables

- `E03_*`: `d_model` hidden width; `params` feed-forward block parameters; `prove_s` proving time; `peak_rss_gib` peak resident memory in GiB.
- `E05_packed_*`: `batch_B` concurrent requests; `packed_prove_s` time of one packed proof; `separate_prove_s_*` separate proofs of the same model (measured for B = 3 only; the B = 6 and 12 baselines are derived as B x the measured single proof).
- `E07_*`: the four percentages are first-token / per-token / whole-sentence / teacher-forced agreement with the f32 model over 16 prompts not used in calibration, 8 generated tokens each.
- `E09_*_cumulative_by_window`: cumulative metrics logged every 10 windows; `argmax_agree_pct` is per-position top-1 agreement between the quantized and f32 models; `kl_nats` is the mean per-position KL(f32 || quantized).
- `E10_*`: `samples_s` is the sample size (1000 means all 47 chunks); `seal_and_prove_s` includes sealing all 47 boundaries.
- `E11_*`: the three fingerprint prefixes are calibration digest, quantized-weight fingerprint, activation-scale fingerprint; `repeat1/2` say whether an in-process repeated inference on the same input matched the first run token for token.
- `E12_*`: `q_escape_prob` is the theoretical probability that one sample avoids all forged chunks; `measured_mean_trials` is the attacker's mean number of re-sealing attempts without a beacon; `beacon_escape_frac` is the measured escape fraction over 2,000 random beacons with a beacon.

## Rebuild

```
python3 tools/build_dataset.py <archive root containing gpu-run-archive/ and 70b-run-archive/>
```

## Notes

- All figures are single measured runs without repetition, except the statistics in E09 and E12 (see column notes).
- Models and datasets are public releases: GPT-2 (Q8_0 GGUF), TinyLlama/TinyLlama-1.1B-Chat-v1.0, Llama-2-70B, WikiText-2 raw v1.
- Data licence: to be determined (CC BY 4.0 suggested).
