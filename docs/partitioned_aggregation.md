# Partitioned aggregation

Large FL models exceed SGX EPC limits (~128MB). CCFL splits the flattened weight vector into partitions (default 50,000 floats per partition).

For each partition:

1. Slice client updates to `[start, end)`
2. Run AHDA independently on the slice
3. Clients rejected in any partition are marked rejected globally
4. Concatenate partition averages into the global vector

Enable via `PUT /model/aggregate_weights_local?partitioned=true` or `partitioned: true` in experiment YAML.

Timing is returned in `aggregation.elapsed_ms` for scalability plots.
