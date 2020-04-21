class StackableBarChart extends BarChart{
    constructor(container_name, data) {
        super(container_name, data);
        this.x = d3.scaleBand()
            .domain(data.map(d => d.name))
            .range([margin.left, width - margin.right])
            .padding(0.1)
        this.y = d3.scaleLinear()
            .domain([0, d3.max(series, d => d3.max(d, d => d[1]))])
            .rangeRound([height - margin.bottom, margin.top])
        this.color = d3.scaleOrdinal()
            .domain(series.map(d => d.key))
            .range(d3.schemeSpectral[series.length])
            .unknown("#ccc")
        this.xAxis = g => g
            .attr("transform", `translate(0,${height - margin.bottom})`)
            .call(d3.axisBottom(x).tickSizeOuter(0))
            .call(g => g.selectAll(".domain").remove())
        this.yAxis = g => g
            .attr("transform", `translate(${margin.left},0)`)
            .call(d3.axisLeft(y).ticks(null, "s"))
            .call(g => g.selectAll(".domain").remove())
        this.buildSVG()
    }
    buildSVG(){
        const svg = d3.create("svg")
            .attr("viewBox", [0, 0, width, height]);
        let formatValue = x => isNaN(x) ? "N/A" : x.toLocaleString("en")
        svg.append("g")
            .selectAll("g")
            .data(series)
            .join("g")
            .attr("fill", d => this.color(d.key))
            .selectAll("rect")
            .data(d => d)
            .join("rect")
            .attr("x", (d, i) => x(d.data.name))
            .attr("y", d => y(d[1]))
            .attr("height", d => y(d[0]) - y(d[1]))
            .attr("width", this.x.bandwidth())
            .append("title")
            .text(d => `${d.data.name} ${d.key} ${formatValue(d.data[d.key])}`);

        svg.append("g")
            .call(this.xAxis);

        svg.append("g")
            .call(this.yAxis);

    }

}