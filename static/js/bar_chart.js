
function plotBar(graphData){
    const width_margin = 120;
    const height_margin = 60;
    const height = 500 - 2 * height_margin;
    const width = 800 - 2 * width_margin;
    const maxValue = Math.max.apply(Math, graphData.map(function(o) { return o.value; }))

    const svg = d3.select('svg');
    const chart = svg.append('g')
        .attr('transform', `translate(${width_margin}, ${height_margin})`);
    const yScale = d3.scaleBand()
        .range([0, height])
        .domain(graphData.map((s) => s.sector))
        .padding(0.3)
    const xScale = d3.scaleLinear()
        .range([0, width])
        .domain([0, maxValue * 1.2])
    chart.append('g')
        .call(d3.axisLeft(yScale))
        .selectAll("text")
            .style("text-anchor", "end")
            .attr("transform", "rotate(-25)");
    chart.append('g')
        .call(d3.axisTop(xScale));
    chart.selectAll()
        .data(graphData)
        .enter()
        .append('rect')
        .attr('class', 'bar')
        .attr('x', (s) => 0)
        .attr('y', (s) => yScale(s.sector))
        .attr('height', yScale.bandwidth())
        .attr('width', (s) => xScale(s.value))
        .on('mouseenter', function (actual, i) {
            d3.select(this).attr('opacity', 0.5)
            const x = xScale(actual.value)
            chart.append('line')
                .attr('id', 'limit')
                .attr('x1', x)
                .attr('y1', 0)
                .attr('x2', x)
                .attr('y2', height)
                .attr('stroke', 'red')
        })
        .on('mouseleave', function (actual, i) {
            d3.select(this).attr('opacity', 1)
            chart.selectAll('#limit').remove()
        })
    svg.append('text')
        .attr('x', -(height / 2) - width_margin)
        .attr('y', height_margin / 2.4)
        .attr('transform', 'rotate(-90)')
        .attr('text-anchor', 'middle')
        .text('Sectors')
    svg.append('text')
        .attr('x', width / 2 + width_margin)
        .attr('y', 20)
        .attr('text-anchor', 'middle')
        .text('Amount')
      

}

