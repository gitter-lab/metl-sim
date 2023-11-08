CREATE TABLE IF NOT EXISTS  `variant` (
    `pdb_fn` TEXT NOT NULL,
    `mutations` TEXT NOT NULL,
    `job_uuid` TEXT NOT NULL,
    `start_time` TEXT,
    `run_time` INTEGER,
    `mutate_run_time` INTEGER,
    `dock_run_time` INTEGER,

    `total_score` REAL,
    `complex_normalized` REAL,
    `dG_cross` REAL,
    `dG_cross/dSASAx100` REAL,
    `dG_separated` REAL,
    `dG_separated/dSASAx100` REAL,
    `dSASA_hphobic` REAL,
    `dSASA_int` REAL,
    `dSASA_polar` REAL,
    `delta_unsatHbonds` REAL,
    `dslf_fa13` REAL,
    `fa_atr` REAL,
    `fa_dun` REAL,
    `fa_elec` REAL,
    `fa_intra_rep` REAL,
    `fa_intra_sol_xover4` REAL,
    `fa_rep` REAL,
    `fa_sol` REAL,
    `hbond_E_fraction` REAL,
    `hbond_bb_sc` REAL,
    `hbond_lr_bb` REAL,
    `hbond_sc` REAL,
    `hbond_sr_bb` REAL,
    `hbonds_int` REAL,
    `lk_ball_wtd` REAL,
    `nres_all` REAL,
    `nres_int` REAL,
    `omega` REAL,
    `p_aa_pp` REAL,
    `packstat` REAL,
    `per_residue_energy_int` REAL,
    `pro_close` REAL,
    `rama_prepro` REAL,
    `ref` REAL,
    `sc_value` REAL,
    `side1_normalized` REAL,
    `side1_score` REAL,
    `side2_normalized` REAL,
    `side2_score` REAL,
    `yhh_planarity` REAL,

    PRIMARY KEY (`pdb_fn`,`mutations`,`job_uuid`),
    FOREIGN KEY (`pdb_fn`) REFERENCES pdb_file(`pdb_fn`),
    FOREIGN KEY (`job_uuid`) REFERENCES job(`uuid`));

CREATE INDEX mutations_index ON variant(mutations);
CREATE INDEX pdb_fn_index ON variant(pdb_fn);
CREATE INDEX job_uuid_index ON variant(job_uuid);

CREATE TABLE IF NOT EXISTS  `pdb_file` (
    `pdb_fn` TEXT,
    `aa_sequence` TEXT,
    `seq_len` INTEGER,
    PRIMARY KEY (`pdb_fn`));

CREATE INDEX  pdb_file_pdb_fn_index ON pdb_file(pdb_fn);

CREATE TABLE IF NOT EXISTS  `job` (
    `uuid` TEXT,
    `cluster` TEXT,
    `process` TEXT,
    `hostname` TEXT,
    `github_tag` TEXT,
    `script_start_time` TEXT,
    `hp_num_structs` INTEGER,
    PRIMARY KEY (`uuid`));


CREATE INDEX job_job_uuid_index ON job(uuid);
CREATE INDEX job_cluster_index ON job(cluster);
CREATE INDEX job_process_index ON job(process);
CREATE INDEX job_cluster_process_index ON job(cluster, process)
