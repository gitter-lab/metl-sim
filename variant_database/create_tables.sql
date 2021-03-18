CREATE TABLE IF NOT EXISTS  `variant` (
    `pdb_fn` VARCHAR NOT NULL,
    `mutations` VARCHAR NOT NULL,
    `job_uuid` VARCHAR NOT NULL,
    `start_time` DATETIME,
    `run_time` INT unsigned,
    `total_score` DECIMAL NOT NULL,
    `dslf_fa13` DECIMAL NOT NULL,
    `fa_atr` DECIMAL NOT NULL,
    `fa_dun` DECIMAL NOT NULL,
    `fa_elec` DECIMAL NOT NULL,
    `fa_intra_rep` DECIMAL NOT NULL,
    `fa_intra_sol_xover4` DECIMAL NOT NULL,
    `fa_rep` DECIMAL NOT NULL,
    `fa_sol` DECIMAL NOT NULL,
    `hbond_bb_sc` DECIMAL NOT NULL,
    `hbond_lr_bb` DECIMAL NOT NULL,
    `hbond_sc` DECIMAL NOT NULL,
    `hbond_sr_bb` DECIMAL NOT NULL,
    `lk_ball_wtd` DECIMAL NOT NULL,
    `omega` DECIMAL NOT NULL,
    `p_aa_pp` DECIMAL NOT NULL,
    `pro_close` DECIMAL NOT NULL,
    `rama_prepro` DECIMAL NOT NULL,
    `ref` DECIMAL NOT NULL,
    `yhh_planarity` DECIMAL NOT NULL,
    PRIMARY KEY (`pdb_fn`,`mutations`,`job_uuid`)
    FOREIGN KEY (`pdb_fn`) REFERENCES pdb_file(`pdb_fn`)
    FOREIGN KEY (`job_uuid`) REFERENCES job(`uuid`));

CREATE TABLE IF NOT EXISTS  `pdb_file` (
    `pdb_fn` VARCHAR NOT NULL,
    `aa_sequence` VARCHAR NOT NULL,
    `seq_len` INT unsigned NOT NULL,
    PRIMARY KEY (`pdb_fn`));

CREATE TABLE IF NOT EXISTS  `job` (
    `uuid` VARCHAR NOT NULL,
    `hparam_set_id` VARCHAR NOT NULL,
    `cluster` VARCHAR NOT NULL,
    `process` VARCHAR NOT NULL,
    `hostname` VARCHAR NOT NULL,
    `github_tag` VARCHAR NOT NULL,
    `script_start_time` DATETIME NOT NULL,
    PRIMARY KEY (`uuid`)
    FOREIGN KEY (`hparam_set_id`) REFERENCES rosetta_hparam_set(`id`));

CREATE TABLE IF NOT EXISTS  `rosetta_hparam_set` (
    `id` INT unsigned AUTO_INCREMENT NOT NULL,
    `mutate_default_max_cycles` INT unsigned NOT NULL,
    `relax_repeats` INT unsigned NOT NULL,
    `relax_nstruct` INT unsigned NOT NULL,
    `relax_distance` DECIMAL NOT NULL,
    PRIMARY KEY (`id`));