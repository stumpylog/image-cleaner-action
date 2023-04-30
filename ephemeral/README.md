# Ephemeral Image Cleaner Action

| Input        | Type    | Description                                                                                             |
| ------------ | ------- | ------------------------------------------------------------------------------------------------------- |
| token        | string  | A Personal Access Token with OAuth scope for packages:delete (if delete is set)                         |
| owner        | string  | The owner of the package                                                                                |
| is_org       | boolean | If the owner is a organization, this must be set True                                                   |
| package_name | string  | The name of the package to run against                                                                  |
| do_delete    | boolean | If set True, the action will actually delete the package                                                |
| log_level    | string  | The logging level, based on Python log levels (defaults to "info")                                      |
| repo_name    | string  | The repository which is the source of the images                                                        |
| scheme       | string  | One of "branch" or "pull_request", describing how the images have been named                            |
| match_regex  | string  | A regular expression, with matching group(s) to extract a pull request number (if using "pull_request") |
