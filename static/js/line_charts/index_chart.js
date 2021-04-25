class IndexChart {
    duration = 500;
    constructor(container_name, data, margin = ({top: 30, right: 30, bottom: 30, left: 30})) {
        this.root = this.transformData(data)
        this.c_name = container_name
        this.margin = margin
        this.container = d3.select(container_name)
        this.width = this.container.node().getBoundingClientRect().width - this.margin.right;
        this.height = this.getHeight()
        this.container.style("height", (this.height + this.margin.bottom + this.margin.top) + "px");
        this.buildSVG()
    }

    buildSVG() {
        let k = d3.max(d3.group(data, d => d.name), ([, group]) => d3.max(group, d => d.value) / d3.min(group, d => d.value))
        let x = d3.scaleUtc()
            .domain(d3.extent(data, d => d.date))
            .range([this.margin.left, this.width - this.margin.right])
            .clamp(true)
        let y = d3.scaleLog()
            .domain([1 / k, k])
            .rangeRound([this.height - this.margin.bottom, this.margin.top])
        let z = d3.scaleOrdinal(d3.schemeCategory10).domain(data.map(d => d.name))
        let xAxis = g => g
            .attr("transform", `translate(0,${this.height - this.margin.bottom})`)
            .call(d3.axisBottom(x).ticks(this.width / 80).tickSizeOuter(0))
            .call(g => g.select(".domain").remove())
        let yAxis = g => g
            .attr("transform", `translate(${this.margin.left},0)`)
            .call(d3.axisLeft(y)
                .ticks(null, x => +x.toFixed(6) + "×"))
            .call(g => g.selectAll(".tick line").clone()
                .attr("stroke-opacity", d => d === 1 ? null : 0.2)
                .attr("x2", this.width - this.margin.left - this.margin.right))
            .call(g => g.select(".domain").remove())
        let line = d3.line()
            .x(d => x(d.date))
            .y(d => y(d.value))
        let bisect = d3.bisector(d => d.date).left
        const svg = d3.select(DOM.svg(this.width, this.height))
            .style("-webkit-tap-highlight-color", "transparent")
            .on("mousemove touchmove", moved);

        svg.append("g")
            .call(xAxis);

        svg.append("g")
            .call(yAxis);

        const rule = svg.append("g")
            .append("line")
            .attr("y1", this.height)
            .attr("y2", 0)
            .attr("stroke", "black");

        const serie = svg.append("g")
            .style("font", "bold 10px sans-serif")
            .selectAll("g")
            .data(this.root)
            .join("g");

        serie.append("path")
            .attr("fill", "none")
            .attr("stroke-width", 1.5)
            .attr("stroke-linejoin", "round")
            .attr("stroke-linecap", "round")
            .attr("stroke", d => z(d.key))
            .attr("d", d => line(d.values));


        serie.append("text")
            .datum(d => ({key: d.key, value: d.values[d.values.length - 1].value}))
            .attr("fill", "none")
            .attr("stroke", "white")
            .attr("stroke-width", 3)
            .attr("x", x.range()[1] + 3)
            .attr("y", d => y(d.value))
            .attr("dy", "0.35em")
            .text(d => d.key)
            .clone(true)
            .attr("fill", d => z(d.key))
            .attr("stroke", null);

        d3.transition()
            .ease(d3.easeCubicOut)
            .duration(1500)
            .tween("date", () => {
                const i = d3.interpolateDate(x.domain()[1], x.domain()[0]);
                return t => update(i(t));
            });

        function update(date) {
            date = d3.utcDay.round(date);
            rule.attr("transform", `translate(${x(date) + 0.5},0)`);
            serie.attr("transform", ({values}) => {
                const i = bisect(values, date, 0, values.length - 1);
                return `translate(0,${y(1) - y(values[i].value / values[0].value)})`;
            });
            svg.property("value", date).dispatch("input");
        }

        function moved() {
            update(x.invert(d3.mouse(this)[0]));
            d3.event.preventDefault();
        }

        update(x.domain()[0]);
    }

    getHeight() {
        return 0;
    }

    transformData(data) {
        let parseDate = d3.utcParse("%Y-%m-%d")
        return data.forEach((d, i, value) => {
            return value.forEach((el) => {
                const date = parseDate(el["Date"]);
                return {"date": date, "value": +el["Close"]}
            })
        });
    };

}