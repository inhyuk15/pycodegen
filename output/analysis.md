# pass@1 Analysis (gpt-5.4-mini, 1323 samples)

## 1. Overall pass@1

| Variant | Pass | Total | Rate |
|---------|-----:|------:|-----:|
| without | 60 | 1323 | 4.5% |
| sd_sd | 417 | 1323 | 31.5% |
| full_full | 715 | 1323 | 54.0% |

## 2. Context monotonicity (more context should help)

Expected order: without < sd_sd < full_full

| Comparison | Both pass | A only (violation) | B only (improvement) | Both fail |
|------------|----------:|-------------------:|---------------------:|----------:|
| without → sd_sd | 40 | 20 | 377 | 886 |
| sd_sd → full_full | 383 | 34 | 332 | 574 |
| without → full_full | 35 | 25 | 680 | 583 |

## 3. Monotonicity violations

### without Pass → sd_sd Fail (20 cases)

| Namespace | Deps | Prompt size (without) | Prompt size (sd_sd) | Ratio |
|-----------|-----:|-----------------:|-----------------:|------:|
| OpenSSL.rand.add | 1 | 582 | 724 | 1.2x |
| boltons.strutils.asciify | 1 | 613 | 787 | 1.3x |
| boto.ec2.connect_to_region | 3 | 584 | 107940 | 184.8x |
| boto.glacier.utils.minimum_part_size | 3 | 826 | 1042 | 1.3x |
| boto.opsworks.regions | 2 | 415 | 94051 | 226.6x |
| fs._url_tools.url_quote | 2 | 552 | 1065 | 1.9x |
| mingus.core.intervals.measure | 2 | 487 | 1012 | 2.1x |
| mingus.core.notes.remove_redundant_accidentals | 2 | 425 | 782 | 1.8x |
| mrjob.py2.to_unicode | 1 | 478 | 631 | 1.3x |
| mrjob.util.safeeval | 1 | 784 | 941 | 1.2x |
| pycoin.bloomfilter.murmur3 | 1 | 479 | 635 | 1.3x |
| pycoin.message.PeerAddress.ip_bin_to_ip4_addr | 1 | 527 | 702 | 1.3x |
| pycoin.satoshi.stackops.do_OP_HASH256 | 1 | 387 | 580 | 1.5x |
| pycoin.satoshi.stackops.do_OP_RIPEMD160 | 1 | 408 | 565 | 1.4x |
| pysnooper.utils.ensure_tuple | 1 | 497 | 643 | 1.3x |
| sslyze.plugins.certificate_info._cli_connector._get_name_as_short_text | 1 | 651 | 836 | 1.3x |
| sumy.nlp.stemmers.null_stemmer | 1 | 418 | 574 | 1.4x |
| tools.cgrep.is_valid_ip | 2 | 604 | 1649 | 2.7x |
| viztracer.code_monkey.AstTransformer.get_assign_targets_with_attr | 1 | 1237 | 1419 | 1.1x |
| zxcvbn.matching.sequence_match | 1 | 1525 | 1674 | 1.1x |

### sd_sd Pass → full_full Fail (34 cases)

| Namespace | Deps | Prompt size (sd_sd) | Prompt size (full_full) | Ratio |
|-----------|-----:|-----------------:|-----------------:|------:|
| alembic.autogenerate.render._render_unique_constraint | 3 | 4196 | 11320 | 2.7x |
| alembic.util.sqla_compat._get_constraint_final_name | 1 | 1158 | 1158 | 1.0x |
| benedict.dicts.keypath.keypath_util._split_key_indexes | 1 | 776 | 776 | 1.0x |
| boltons.cacheutils.LRI.clear | 2 | 4129 | 16342 | 4.0x |
| boto.dynamodb2.table.Table.describe | 10 | 430972 | 673610 | 1.6x |
| boto.ec2.securitygroup.SecurityGroup.add_rule | 7 | 7055 | 19658 | 2.8x |
| datasette.utils.validate_sql_select | 3 | 1492 | 1501 | 1.0x |
| faker.utils.loading.find_available_locales | 1 | 881 | 1142 | 1.3x |
| feedparser.http._build_urllib2_request | 1 | 1380 | 1745 | 1.3x |
| feedparser.urls.make_safe_absolute_uri | 2 | 1451 | 1591 | 1.1x |
| imapclient.datetime_util.parse_to_datetime | 3 | 1607 | 2313 | 1.4x |
| mingus.core.notes.reduce_accidentals | 3 | 1084 | 2003 | 1.8x |
| mopidy.internal.network.try_ipv6_socket | 1 | 687 | 687 | 1.0x |
| mopidy.models.immutable.ValidatedImmutableObject.replace | 2 | 4009 | 8639 | 2.2x |
| mrjob.conf.combine_jobconfs | 2 | 1109 | 1793 | 1.6x |
| mrjob.fs.local.LocalFilesystem.touchz | 1 | 685 | 904 | 1.3x |
| mrjob.job.MRJob.sandbox | 3 | 86016 | 176875 | 2.1x |
| mssqlcli.jsonrpc.jsonrpcclient.JsonRpcClient.shutdown | 6 | 8957 | 28029 | 3.1x |
| mssqlcli.telemetry.conclude | 5 | 1854 | 8599 | 4.6x |
| playhouse.sqlite_changelog.ChangeLog.install | 5 | 9517 | 24042 | 2.5x |
| pycoin.bloomfilter.filter_size_required | 1 | 1239 | 1239 | 1.0x |
| pycoin.contrib.bech32m.bech32_encode | 1 | 877 | 1100 | 1.3x |
| pyt.__main__.discover_files | 1 | 997 | 997 | 1.0x |
| rest_framework.reverse.reverse | 3 | 1995 | 2836 | 1.4x |
| rest_framework.templatetags.rest_framework.add_query_param | 1 | 990 | 1323 | 1.3x |
| sslyze.plugins.certificate_info._cli_connector._CertificateInfoCliConnector.result_to_console_output | 5 | 6050 | 20206 | 3.3x |
| sslyze.plugins.session_renegotiation_plugin._SessionRenegotiationCliConnector.result_to_console_output | 5 | 4657 | 6080 | 1.3x |
| telethon.extensions.html.unparse | 4 | 2189 | 2820 | 1.3x |
| twilio.twiml.voice_response.VoiceResponse.gather | 3 | 5985 | 8231 | 1.4x |
| whereami.predict.crossval | 2 | 2195 | 2885 | 1.3x |
| ydata_profiling.model.pandas.correlations_pandas.pandas_cramers_compute | 3 | 5010 | 7465 | 1.5x |
| zulipterminal.config.keys.is_command_key | 2 | 12145 | 12154 | 1.0x |
| zxcvbn.matching.dictionary_match | 1 | 999 | 999 | 1.0x |
| zxcvbn.time_estimates.estimate_attack_times | 3 | 1030 | 3122 | 3.0x |

### without Pass → full_full Fail (25 cases)

| Namespace | Deps | Prompt size (without) | Prompt size (full_full) | Ratio |
|-----------|-----:|-----------------:|-----------------:|------:|
| OpenSSL.rand.add | 1 | 582 | 724 | 1.2x |
| boltons.strutils.asciify | 1 | 613 | 787 | 1.3x |
| boto.ec2.connect_to_region | 3 | 584 | 179073 | 306.6x |
| boto.glacier.utils.minimum_part_size | 3 | 826 | 1042 | 1.3x |
| boto.opsworks.regions | 2 | 415 | 130563 | 314.6x |
| feedparser.http._build_urllib2_request | 1 | 1153 | 1745 | 1.5x |
| fs._url_tools.url_quote | 2 | 552 | 1240 | 2.2x |
| mingus.core.intervals.measure | 2 | 487 | 1650 | 3.4x |
| mingus.core.notes.remove_redundant_accidentals | 2 | 425 | 986 | 2.3x |
| mrjob.py2.to_unicode | 1 | 478 | 631 | 1.3x |
| mrjob.util.safeeval | 1 | 784 | 941 | 1.2x |
| pycoin.bloomfilter.murmur3 | 1 | 479 | 650 | 1.4x |
| pycoin.contrib.bech32m.bech32_encode | 1 | 642 | 1100 | 1.7x |
| pycoin.message.PeerAddress.ip_bin_to_ip4_addr | 1 | 527 | 702 | 1.3x |
| pycoin.satoshi.stackops.do_OP_HASH256 | 1 | 387 | 655 | 1.7x |
| pycoin.satoshi.stackops.do_OP_RIPEMD160 | 1 | 408 | 565 | 1.4x |
| pysnooper.utils.ensure_tuple | 1 | 497 | 643 | 1.3x |
| rest_framework.reverse.reverse | 3 | 943 | 2836 | 3.0x |
| sslyze.plugins.certificate_info._cli_connector._get_name_as_short_text | 1 | 651 | 931 | 1.4x |
| sumy.nlp.stemmers.null_stemmer | 1 | 418 | 792 | 1.9x |
| tools.cgrep.is_valid_ip | 2 | 604 | 2549 | 4.2x |
| whereami.predict.crossval | 2 | 1995 | 2885 | 1.4x |
| zxcvbn.matching.dictionary_match | 1 | 850 | 999 | 1.2x |
| zxcvbn.matching.sequence_match | 1 | 1525 | 1674 | 1.1x |
| zxcvbn.time_estimates.estimate_attack_times | 3 | 714 | 3122 | 4.4x |

## 4. sd_sd vs full_full

- sd_sd only pass: **34** (context noise)
- full_full only pass: **332** (more context helped)
- Net gain from full: **+298**

#### Prompt size ratio (full/sd) for sd-only wins:

| Range | Count |
|-------|------:|
| 1.0x (identical) | 8 |
| 1.1x ~ 1.5x | 13 |
| 1.5x ~ 2.0x | 3 |
| 2.0x ~ 3.0x | 5 |
| 3.0x+ | 5 |
| **Average** | **1.8x** |

## 5. Pass/fail patterns

| without | sd_sd | full_full | Count | % |
|------|------|------|------:|----:|
| F | F | F | 555 | 42.0% |
| F | P | P | 349 | 26.4% |
| F | F | P | 331 | 25.0% |
| P | P | P | 34 | 2.6% |
| F | P | F | 28 | 2.1% |
| P | F | F | 19 | 1.4% |
| P | P | F | 6 | 0.5% |
| P | F | P | 1 | 0.1% |

## 6. Per-repo pass rates (repos with 5+ samples)

| Repo | Samples | without | sd_sd | full_full |
|------|--------:|------:|------:|------:|
| boto | 117 | 3% | 27% | 59% |
| mrjob | 90 | 4% | 39% | 63% |
| pyramid | 89 | 0% | 0% | 0% |
| boltons | 81 | 4% | 54% | 88% |
| alembic | 50 | 0% | 24% | 66% |
| mingus | 45 | 16% | 38% | 62% |
| falcon | 40 | 2% | 50% | 82% |
| mopidy | 37 | 0% | 24% | 54% |
| zulipterminal | 32 | 0% | 22% | 50% |
| datasette | 31 | 6% | 16% | 26% |
| imapclient | 31 | 0% | 16% | 87% |
| pythonforandroid | 31 | 0% | 29% | 55% |
| bentoml | 30 | 3% | 27% | 30% |
| kinto | 30 | 0% | 0% | 0% |
| sacred | 30 | 13% | 37% | 53% |
| diffprivlib | 26 | 0% | 50% | 92% |
| twilio | 25 | 0% | 44% | 80% |
| fs | 24 | 8% | 46% | 79% |
| rest_framework | 24 | 4% | 38% | 67% |
| sumy | 24 | 8% | 8% | 8% |
| msticpy | 19 | 0% | 0% | 0% |
| pycoin | 18 | 28% | 28% | 39% |
| mssqlcli | 16 | 6% | 62% | 69% |
| bplustree | 14 | 0% | 36% | 100% |
| chatette | 14 | 7% | 21% | 57% |
| dash | 14 | 7% | 21% | 50% |
| gunicorn | 14 | 0% | 0% | 0% |
| zxcvbn | 14 | 21% | 36% | 21% |
| exodus_bundler | 13 | 8% | 31% | 62% |
| jinja2 | 13 | 0% | 62% | 92% |
| wikipediaapi | 13 | 0% | 54% | 100% |
| barf | 12 | 0% | 0% | 0% |
| praw | 12 | 0% | 58% | 100% |
| pyinfra | 12 | 0% | 0% | 0% |
| asyncssh | 11 | 0% | 64% | 82% |
| ydata_profiling | 11 | 9% | 45% | 36% |
| googleapiclient | 9 | 11% | 56% | 78% |
| playhouse | 9 | 0% | 44% | 89% |
| sslyze | 9 | 11% | 44% | 33% |
| oletools | 8 | 12% | 62% | 62% |
| trailscraper | 8 | 0% | 0% | 0% |
| twtxt | 8 | 0% | 50% | 88% |
| authlib | 7 | 14% | 71% | 71% |
| faker | 7 | 0% | 57% | 43% |
| hl7 | 7 | 0% | 57% | 100% |
| rows | 7 | 0% | 71% | 100% |
| jc | 6 | 0% | 0% | 0% |
| pyt | 6 | 0% | 50% | 67% |
| wal_e | 6 | 0% | 0% | 0% |
| discord | 5 | 0% | 40% | 80% |
| ehforwarderbot | 5 | 0% | 0% | 0% |
| jwt | 5 | 0% | 80% | 80% |
| mackup | 5 | 0% | 40% | 60% |
| prometheus_client | 5 | 0% | 40% | 80% |
| sqlitedict | 5 | 20% | 100% | 100% |
| viztracer | 5 | 20% | 20% | 100% |
